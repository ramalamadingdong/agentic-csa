"""Plugin discovery and loading system."""

import importlib
import importlib.util
import json
import logging
from pathlib import Path
from typing import Any, Optional

from .plugins.base import PluginBase, PluginConfig


logger = logging.getLogger(__name__)


class PluginLoadError(Exception):
    """Raised when a plugin fails to load."""
    pass


class PluginLoader:
    """
    Discovers and loads documentation plugins.
    
    Plugins are Python modules in the plugins/ directory that
    export a class inheriting from PluginBase.
    """
    
    PLUGIN_ENTRY_POINT = "plugin.py"
    PLUGIN_CLASS_ATTR = "Plugin"
    
    def __init__(self, plugins_dir: Optional[Path] = None):
        """
        Initialize the plugin loader.
        
        Args:
            plugins_dir: Directory containing plugins (default: built-in plugins dir)
        """
        if plugins_dir is None:
            plugins_dir = Path(__file__).parent / "plugins"
        
        self.plugins_dir = plugins_dir
        self._plugins: dict[str, PluginBase] = {}
        self._load_errors: dict[str, str] = {}
    
    def discover_plugins(self) -> list[str]:
        """
        Discover available plugins in the plugins directory.
        
        Returns:
            List of plugin names that can be loaded
        """
        plugins = []
        
        if not self.plugins_dir.exists():
            logger.warning(f"Plugins directory not found: {self.plugins_dir}")
            return plugins
        
        for item in self.plugins_dir.iterdir():
            if item.is_dir() and not item.name.startswith("_"):
                plugin_file = item / self.PLUGIN_ENTRY_POINT
                if plugin_file.exists():
                    plugins.append(item.name)
        
        return sorted(plugins)
    
    def load_plugin(self, name: str) -> Optional[PluginBase]:
        """
        Load a single plugin by name.
        
        Args:
            name: Plugin name (directory name in plugins/)
            
        Returns:
            Plugin instance if successful, None if failed
            
        Raises:
            PluginLoadError: If plugin cannot be loaded
        """
        if name in self._plugins:
            return self._plugins[name]
        
        plugin_dir = self.plugins_dir / name
        plugin_file = plugin_dir / self.PLUGIN_ENTRY_POINT
        
        if not plugin_file.exists():
            error = f"Plugin file not found: {plugin_file}"
            self._load_errors[name] = error
            raise PluginLoadError(error)
        
        try:
            # Load the module
            spec = importlib.util.spec_from_file_location(
                f"wpilib_mcp.plugins.{name}.plugin",
                plugin_file
            )
            if spec is None or spec.loader is None:
                raise PluginLoadError(f"Could not create module spec for {name}")
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Get the Plugin class
            if not hasattr(module, self.PLUGIN_CLASS_ATTR):
                raise PluginLoadError(
                    f"Plugin {name} missing '{self.PLUGIN_CLASS_ATTR}' class"
                )
            
            plugin_class = getattr(module, self.PLUGIN_CLASS_ATTR)
            
            # Verify it's a proper plugin
            if not issubclass(plugin_class, PluginBase):
                raise PluginLoadError(
                    f"Plugin {name} class does not inherit from PluginBase"
                )
            
            # Instantiate
            plugin = plugin_class()
            self._plugins[name] = plugin
            
            logger.info(f"Loaded plugin: {plugin.display_name} ({name})")
            return plugin
            
        except PluginLoadError:
            raise
        except Exception as e:
            error = f"Error loading plugin {name}: {e}"
            self._load_errors[name] = error
            logger.error(error, exc_info=True)
            raise PluginLoadError(error) from e
    
    async def load_and_initialize_plugins(
        self,
        config: dict[str, Any],
        fail_fast: bool = False
    ) -> dict[str, PluginBase]:
        """
        Load and initialize all enabled plugins from configuration.
        
        Args:
            config: Full configuration dict with 'plugins' key
            fail_fast: If True, raise on first error; if False, continue loading
            
        Returns:
            Dictionary of initialized plugins by name
        """
        plugins_config = config.get("plugins", {})
        loaded = {}
        
        # Discover available plugins
        available = self.discover_plugins()
        logger.info(f"Discovered plugins: {available}")
        
        for plugin_name in available:
            plugin_conf = plugins_config.get(plugin_name, {})
            
            # Skip disabled plugins
            if not plugin_conf.get("enabled", True):
                logger.info(f"Plugin {plugin_name} is disabled, skipping")
                continue
            
            try:
                # Load the plugin
                plugin = self.load_plugin(plugin_name)
                if plugin is None:
                    continue
                
                # Create config object
                pc = PluginConfig(
                    enabled=True,
                    versions=plugin_conf.get("versions", plugin.supported_versions[:1]),
                    languages=plugin_conf.get("languages", plugin.supported_languages),
                    custom=plugin_conf.get("custom", {})
                )
                
                # Initialize
                await plugin.initialize(pc)
                loaded[plugin_name] = plugin
                
                logger.info(
                    f"Initialized plugin: {plugin.display_name} "
                    f"(versions={pc.versions}, languages={pc.languages})"
                )
                
            except Exception as e:
                error = f"Failed to initialize plugin {plugin_name}: {e}"
                self._load_errors[plugin_name] = error
                logger.error(error, exc_info=True)
                
                if fail_fast:
                    raise PluginLoadError(error) from e
        
        return loaded
    
    def get_plugin(self, name: str) -> Optional[PluginBase]:
        """Get a loaded plugin by name."""
        return self._plugins.get(name)
    
    def get_all_plugins(self) -> dict[str, PluginBase]:
        """Get all loaded plugins."""
        return dict(self._plugins)
    
    def get_initialized_plugins(self) -> dict[str, PluginBase]:
        """Get all plugins that have been successfully initialized."""
        return {
            name: plugin
            for name, plugin in self._plugins.items()
            if plugin.is_initialized
        }
    
    def get_load_errors(self) -> dict[str, str]:
        """Get any plugin load errors that occurred."""
        return dict(self._load_errors)
    
    async def shutdown_all(self) -> None:
        """Shutdown all loaded plugins."""
        for name, plugin in self._plugins.items():
            try:
                await plugin.shutdown()
                logger.info(f"Shutdown plugin: {name}")
            except Exception as e:
                logger.error(f"Error shutting down plugin {name}: {e}")
        
        self._plugins.clear()


def load_config(config_path: Optional[Path] = None) -> dict[str, Any]:
    """
    Load configuration from config.json.
    
    Args:
        config_path: Path to config file (default: project root config.json)
        
    Returns:
        Configuration dictionary
    """
    if config_path is None:
        # Look for config.json in project root
        config_path = Path(__file__).parent.parent.parent.parent / "config.json"
    
    if not config_path.exists():
        logger.warning(f"Config file not found: {config_path}, using defaults")
        return get_default_config()
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        logger.info(f"Loaded configuration from {config_path}")
        return config
    except Exception as e:
        logger.error(f"Error loading config: {e}, using defaults")
        return get_default_config()


def get_default_config() -> dict[str, Any]:
    """Get default configuration."""
    return {
        "plugins": {
            "wpilib": {
                "enabled": True,
                "versions": ["2025"],
                "languages": ["Java", "Python", "C++"]
            }
        },
        "cache": {
            "ttl_seconds": 3600,
            "max_size_mb": 100
        },
        "search": {
            "default_max_results": 10,
            "default_language": "Java",
            "default_version": "2025"
        }
    }





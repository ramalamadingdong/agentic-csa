"""Project context detection for FRC projects.

Detects programming language and vendor libraries from the project structure
to automatically filter and prioritize search results.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ProjectContext:
    """Detected context about an FRC project."""

    language: Optional[str] = None  # "Java", "Python", "C++", or None
    vendors: list[str] = field(default_factory=list)  # ["rev", "ctre", "photonvision", etc.]
    confidence: float = 0.0  # 0.0-1.0 confidence in detection
    detection_sources: list[str] = field(default_factory=list)  # What we found

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "vendors": self.vendors,
            "confidence": self.confidence,
            "detection_sources": self.detection_sources,
        }

    @property
    def has_context(self) -> bool:
        return self.language is not None or len(self.vendors) > 0


# Vendor detection patterns
VENDOR_PATTERNS = {
    "java": {
        "rev": [
            r"import\s+com\.revrobotics\.",
            r"CANSparkMax",
            r"CANSparkFlex",
            r"SparkMaxPIDController",
            r"REVPhysicsSim",
        ],
        "ctre": [
            r"import\s+com\.ctre\.phoenix6?\.",
            r"TalonFX",
            r"CANcoder",
            r"Pigeon2",
            r"StatusSignal",
            r"Phoenix6",
        ],
        "photonvision": [
            r"import\s+org\.photonvision\.",
            r"PhotonCamera",
            r"PhotonPoseEstimator",
            r"PhotonUtils",
        ],
        "redux": [
            r"import\s+com\.reduxrobotics\.",
            r"Canandcoder",
            r"Canandmag",
        ],
        "wpilib": [
            r"import\s+edu\.wpi\.first\.",
            r"import\s+frc\.robot\.",
            r"CommandScheduler",
            r"SubsystemBase",
            r"TimedRobot",
        ],
    },
    "python": {
        "rev": [
            r"import\s+rev",
            r"from\s+rev\s+import",
            r"CANSparkMax",
            r"SparkMaxPIDController",
        ],
        "ctre": [
            r"import\s+phoenix6",
            r"from\s+phoenix6\s+import",
            r"TalonFX",
            r"CANcoder",
        ],
        "photonvision": [
            r"import\s+photonlibpy",
            r"from\s+photonlibpy",
            r"PhotonCamera",
        ],
        "wpilib": [
            r"import\s+wpilib",
            r"from\s+wpilib\s+import",
            r"import\s+commands2",
            r"from\s+commands2\s+import",
        ],
    },
    "cpp": {
        "rev": [
            r'#include\s*[<"]rev/',
            r"rev::CANSparkMax",
            r"rev::spark",
        ],
        "ctre": [
            r'#include\s*[<"]ctre/',
            r"ctre::phoenix6",
            r"ctre::phoenix",
        ],
        "photonvision": [
            r'#include\s*[<"]photon',
            r"photon::PhotonCamera",
        ],
        "wpilib": [
            r'#include\s*[<"]frc/',
            r'#include\s*[<"]frc2/',
            r"frc::TimedRobot",
            r"frc2::CommandScheduler",
        ],
    },
}

# Vendordep JSON patterns (WPILib vendor dependency files)
VENDORDEP_IDENTIFIERS = {
    "rev": ["REVLib", "revrobotics", "REVRobotics"],
    "ctre": ["Phoenix6", "Phoenix5", "CTRE-Phoenix", "ctre"],
    "photonvision": ["photonlib", "PhotonLib", "photonvision"],
    "redux": ["ReduxLib", "reduxrobotics"],
    "navx": ["navx", "kauailabs", "studica"],
    "pathplanner": ["pathplannerlib", "PathplannerLib"],
}


class ProjectContextDetector:
    """Detects FRC project context from source files and build configuration."""

    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize the detector.

        Args:
            project_root: Root directory of the FRC project (defaults to cwd)
        """
        self.project_root = project_root or Path.cwd()
        self._cached_context: Optional[ProjectContext] = None

    def detect(self, force_refresh: bool = False) -> ProjectContext:
        """
        Detect project context.

        Args:
            force_refresh: If True, re-scan even if cached

        Returns:
            ProjectContext with detected language and vendors
        """
        if self._cached_context is not None and not force_refresh:
            return self._cached_context

        context = ProjectContext()
        sources = []

        # Detect language from file extensions
        language, lang_confidence, lang_sources = self._detect_language()
        if language:
            context.language = language
            context.confidence = lang_confidence
            sources.extend(lang_sources)

        # Detect vendors from vendordeps (most reliable)
        vendordep_vendors, vendordep_sources = self._detect_from_vendordeps()
        context.vendors.extend(vendordep_vendors)
        sources.extend(vendordep_sources)

        # Detect vendors from source code imports
        if context.language:
            code_vendors, code_sources = self._detect_from_source_code(context.language)
            for vendor in code_vendors:
                if vendor not in context.vendors:
                    context.vendors.append(vendor)
            sources.extend(code_sources)

        # Detect from build files
        build_vendors, build_sources = self._detect_from_build_files()
        for vendor in build_vendors:
            if vendor not in context.vendors:
                context.vendors.append(vendor)
        sources.extend(build_sources)

        # Update confidence based on detection quality
        if context.vendors:
            context.confidence = min(1.0, context.confidence + 0.2 * len(context.vendors))

        context.detection_sources = sources
        self._cached_context = context
        return context

    def _detect_language(self) -> tuple[Optional[str], float, list[str]]:
        """Detect programming language from file extensions."""
        extensions = {".java": 0, ".py": 0, ".cpp": 0, ".h": 0, ".hpp": 0}
        sources = []

        # Check for language-specific build files first (high confidence)
        if (self.project_root / "build.gradle").exists():
            sources.append("build.gradle found")
            extensions[".java"] += 10
        if (self.project_root / "build.gradle.kts").exists():
            sources.append("build.gradle.kts found")
            extensions[".java"] += 10
        if (self.project_root / "pyproject.toml").exists():
            sources.append("pyproject.toml found")
            extensions[".py"] += 10
        if (self.project_root / "robot.py").exists():
            sources.append("robot.py found")
            extensions[".py"] += 10
        if (self.project_root / "CMakeLists.txt").exists():
            sources.append("CMakeLists.txt found")
            extensions[".cpp"] += 10

        # Count source files
        for ext in extensions:
            try:
                count = len(list(self.project_root.rglob(f"*{ext}")))
                extensions[ext] += count
                if count > 0:
                    sources.append(f"{count} {ext} files")
            except (PermissionError, OSError):
                pass

        # Combine C++ extensions
        cpp_count = extensions[".cpp"] + extensions[".h"] + extensions[".hpp"]

        # Determine language
        if extensions[".java"] > max(extensions[".py"], cpp_count):
            return "Java", min(0.9, extensions[".java"] / 20), sources
        elif extensions[".py"] > max(extensions[".java"], cpp_count):
            return "Python", min(0.9, extensions[".py"] / 20), sources
        elif cpp_count > max(extensions[".java"], extensions[".py"]):
            return "C++", min(0.9, cpp_count / 20), sources

        return None, 0.0, sources

    def _detect_from_vendordeps(self) -> tuple[list[str], list[str]]:
        """Detect vendors from WPILib vendordep JSON files."""
        vendors = []
        sources = []

        vendordeps_dir = self.project_root / "vendordeps"
        if not vendordeps_dir.exists():
            return vendors, sources

        try:
            for json_file in vendordeps_dir.glob("*.json"):
                try:
                    with open(json_file, "r") as f:
                        data = json.load(f)

                    name = data.get("name", "")
                    maven_url = data.get("mavenUrls", [""])[0] if data.get("mavenUrls") else ""
                    uuid = data.get("uuid", "")

                    content = f"{name} {maven_url} {uuid}".lower()

                    for vendor, identifiers in VENDORDEP_IDENTIFIERS.items():
                        for identifier in identifiers:
                            if identifier.lower() in content:
                                if vendor not in vendors:
                                    vendors.append(vendor)
                                    sources.append(f"vendordep: {json_file.name} ({vendor})")
                                break
                except (json.JSONDecodeError, KeyError):
                    pass
        except (PermissionError, OSError):
            pass

        return vendors, sources

    def _detect_from_source_code(self, language: str) -> tuple[list[str], list[str]]:
        """Detect vendors from import statements in source code."""
        vendors = []
        sources = []

        lang_key = language.lower().replace("++", "pp")
        if lang_key not in VENDOR_PATTERNS:
            return vendors, sources

        patterns = VENDOR_PATTERNS[lang_key]

        # Determine file extensions to scan
        if language == "Java":
            extensions = ["*.java"]
            scan_dir = self.project_root / "src"
        elif language == "Python":
            extensions = ["*.py"]
            scan_dir = self.project_root
        else:  # C++
            extensions = ["*.cpp", "*.h", "*.hpp"]
            scan_dir = self.project_root / "src"

        if not scan_dir.exists():
            scan_dir = self.project_root

        # Scan source files (limit to avoid slow scans)
        files_scanned = 0
        max_files = 50

        try:
            for ext in extensions:
                for source_file in scan_dir.rglob(ext):
                    if files_scanned >= max_files:
                        break
                    files_scanned += 1

                    try:
                        content = source_file.read_text(errors="ignore")[:5000]  # First 5KB

                        for vendor, vendor_patterns in patterns.items():
                            if vendor in vendors:
                                continue
                            for pattern in vendor_patterns:
                                if re.search(pattern, content):
                                    vendors.append(vendor)
                                    sources.append(f"import in {source_file.name} ({vendor})")
                                    break
                    except (PermissionError, OSError):
                        pass
        except (PermissionError, OSError):
            pass

        return vendors, sources

    def _detect_from_build_files(self) -> tuple[list[str], list[str]]:
        """Detect vendors from build configuration files."""
        vendors = []
        sources = []

        # Check build.gradle
        for gradle_file in ["build.gradle", "build.gradle.kts"]:
            gradle_path = self.project_root / gradle_file
            if gradle_path.exists():
                try:
                    content = gradle_path.read_text(errors="ignore")
                    for vendor, identifiers in VENDORDEP_IDENTIFIERS.items():
                        for identifier in identifiers:
                            if identifier.lower() in content.lower():
                                if vendor not in vendors:
                                    vendors.append(vendor)
                                    sources.append(f"{gradle_file} dependency ({vendor})")
                                break
                except (PermissionError, OSError):
                    pass

        # Check pyproject.toml for Python
        pyproject_path = self.project_root / "pyproject.toml"
        if pyproject_path.exists():
            try:
                content = pyproject_path.read_text(errors="ignore")
                python_deps = {
                    "rev": ["robotpy-rev", "rev"],
                    "ctre": ["robotpy-ctre", "phoenix6"],
                    "photonvision": ["photonlibpy"],
                    "navx": ["robotpy-navx"],
                }
                for vendor, deps in python_deps.items():
                    for dep in deps:
                        if dep in content.lower():
                            if vendor not in vendors:
                                vendors.append(vendor)
                                sources.append(f"pyproject.toml dependency ({vendor})")
                            break
            except (PermissionError, OSError):
                pass

        return vendors, sources

    def get_search_filters(self) -> dict:
        """
        Get recommended search filters based on detected context.

        Returns:
            Dict with 'language' and 'vendors' keys for search filtering
        """
        context = self.detect()
        filters = {}

        if context.language:
            filters["language"] = context.language

        if context.vendors:
            # Always include wpilib, plus detected vendors
            filters["vendors"] = list(set(["wpilib"] + context.vendors))

        return filters


# Global detector instance (lazily initialized)
_detector: Optional[ProjectContextDetector] = None


def get_project_context(project_root: Optional[Path] = None) -> ProjectContext:
    """
    Get project context, using cached detector if available.

    Args:
        project_root: Project root (uses cwd if not specified)

    Returns:
        Detected ProjectContext
    """
    global _detector

    if project_root:
        # Use fresh detector for specific path
        return ProjectContextDetector(project_root).detect()

    if _detector is None:
        _detector = ProjectContextDetector()

    return _detector.detect()


def get_search_filters(project_root: Optional[Path] = None) -> dict:
    """
    Get recommended search filters for the current project.

    Args:
        project_root: Project root (uses cwd if not specified)

    Returns:
        Dict with 'language' and 'vendors' for filtering
    """
    global _detector

    if project_root:
        return ProjectContextDetector(project_root).get_search_filters()

    if _detector is None:
        _detector = ProjectContextDetector()

    return _detector.get_search_filters()

# FIRST Agentic CSA

<!-- mcp-name: io.github.ramalamadingdong/first-agentic-csa -->

A helpful tool for FIRST Robotics Competition teams! This lets you search through all your FRC documentation (WPILib, REV, CTRE, and more) using simple questions. Instead of clicking through dozens of web pages, just ask a question and get the answer you need.

## What Does This Do?

Have you ever spent hours looking for how to configure a SparkMax motor controller? Or trying to find the right way to use a PID controller? This tool helps you find answers fast by searching through all the FRC documentation at once.

## Features

- **One Search for Everything**: Search WPILib, REV, CTRE, Redux, and PhotonVision docs all at once
- **Ask in Plain English**: Type questions like "How do I configure a SparkMax?" instead of searching through menus
- **Filter by Language**: Get results for Java, Python, or C++ (whichever you're using)
- **Works with Any Year**: Search 2024 docs, 2025 docs, or whatever version you need
- **Works in VS Code**: Set it up once and use it right in your coding environment

## Installation for VS Code

1. Open VS Code
2. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac) to open the command palette
3. Type "MCP: Add Server" and select it
4. Choose "Pip package" from the options
5. When prompted, enter: `first-agentic-csa`
6. VS Code will automatically install and configure everything for you!

### Setting Up GitHub Copilot

To get the best experience with AI coding assistants (like GitHub Copilot or Cursor), add the `copilot-instructions.md` file to your FRC project. This tells the AI to always search the documentation before answering FRC questions.

1. Copy the `copilot-instructions.md` file from this repository
2. Paste it into the root folder of your FRC robot project
3. The AI assistant will automatically use it to provide better, documentation-backed answers!

That's it! Now you can ask questions about FRC documentation right in VS Code, and your AI assistant will automatically search the docs for accurate answers.

## Quick Start

Once installed, you can search for documentation by asking questions like:
- "How do I configure a SparkMax motor controller?"
- "What's the best way to use PID control?"
- "Show me examples of command-based programming"

The tool will search through all the FRC documentation and give you the most relevant results.

## What Documentation Can I Search?

This tool searches through documentation from:

- **WPILib** - The main FRC programming library (docs.wpilib.org)
- **REV Robotics** - SparkMax and other REV products (docs.revrobotics.com)
- **CTRE Phoenix** - TalonFX and other CTRE products (v6.docs.ctr-electronics.com)
- **Redux Robotics** - Redux products (docs.reduxrobotics.com)
- **PhotonVision** - Computer vision library (docs.photonvision.org)

You can search all of them at once, or pick specific ones to search.


## Customization (Optional)

If you want to change settings, you can edit the `config.json` file. This is totally optional - the default settings work great for most teams.

You can:
- Turn off certain documentation sources if you don't use them
- Set your default programming language
- Change how many results you get back

Most teams don't need to change anything - the defaults work well!

## Troubleshooting

### "Command not found" or Server won't start

Make sure you:
1. Have Python 3.11 or newer installed
2. Restarted VS Code after adding the server
3. Checked that the MCP extension is installed and enabled

### Still having issues?

1. Open the command palette (`Ctrl+Shift+P`)
2. Type "MCP: Remove Server" and select it
3. Choose `frc-docs` (or whatever you named it)
4. Then add it again following the installation steps above

## Need Help?

If you're stuck or have questions:
1. Make sure you restarted VS Code after adding the server
2. Check the troubleshooting section above
3. Verify that Python 3.11 or newer is installed and working

## For Advanced Users

If you want to contribute to this project or add support for new documentation sources, check out the technical documentation in the codebase. The project is open source and welcomes contributions!

## License

This project is open source and free to use. See the LICENSE file for details.
/**
 * py.js — Smart Python Executor for Echo FM
 * 
 * Automatically detects and uses the local virtual environment (.venv) if present.
 * Otherwise, falls back to the system 'python' command.
 * 
 * Usage in package.json:
 *   "start": "node scripts/py.js main.py --env local"
 */

const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// 1. Determine paths based on OS
const isWin = process.platform === 'win32';
const venvPath = isWin 
  ? path.join(process.cwd(), '.venv', 'Scripts', 'python.exe') 
  : path.join(process.cwd(), '.venv', 'bin', 'python');

// 2. Select the command
const pythonCmd = fs.existsSync(venvPath) ? venvPath : 'python';

// 3. Extract arguments (excluding 'node' and 'scripts/py.js')
const args = process.argv.slice(2);

// 4. Log for developer clarity (silent in CI/Production usually, but helpful for debugging)
if (process.env.DEBUG) {
  console.log(`[PyRunner] Using: ${pythonCmd}`);
}

// 5. Execute and pass through all I/O
// Quote the command to handle paths with spaces
const quotedPythonCmd = pythonCmd.includes(' ') ? `"${pythonCmd}"` : pythonCmd;

const result = spawnSync(quotedPythonCmd, args, { 
  stdio: 'inherit', 
  shell: true // Required for correctly interpreting the quoted command string
});

// 6. Exit with the same code as Python
process.exit(result.status ?? 0);

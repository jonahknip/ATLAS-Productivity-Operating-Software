/**
 * Security Policy Configuration for ATLAS MCP Autopilot
 * Defines allowed roots, extensions, commands, and blocked patterns.
 */

import { platform, homedir } from 'os';
import { join } from 'path';

const isWindows = platform() === 'win32';
const home = homedir();

// Allowed root directories (cross-platform)
export const ALLOWED_ROOTS: string[] = isWindows
  ? [
      'C:\\atlas\\',
      'C:\\Users\\Jonah\\Documents\\',
      'C:\\Users\\Jonah\\Desktop\\',
    ]
  : [
      join(home, 'projects', 'ATLAS'),
      join(home, 'Documents'),
      join(home, 'Desktop'),
    ];

// Scripts directory (for executable writes)
export const SCRIPTS_DIR: string = isWindows
  ? 'C:\\atlas\\scripts\\'
  : join(home, 'projects', 'ATLAS', 'scripts');

// Allowed file extensions for writing
export const ALLOWED_WRITE_EXTENSIONS: string[] = [
  '.md', '.txt', '.json', '.ts', '.tsx', '.py', '.yaml', '.yml',
  '.js', '.jsx', '.css', '.html', '.csv', '.xml', '.toml',
];

// Denied file extensions (executables/scripts)
export const DENIED_WRITE_EXTENSIONS: string[] = [
  '.exe', '.dll', '.bat', '.cmd', '.ps1', '.sh', '.bash',
  '.com', '.msi', '.scr', '.vbs', '.wsf',
];

// Allowed base commands for shell execution
export const ALLOWED_COMMANDS: string[] = [
  'python', 'python3', 'node', 'npm', 'pnpm', 'npx',
  'git', 'uv', 'pip', 'pip3',
  // Windows
  'dir', 'type', 'echo', 'mkdir', 'copy', 'move', 'ren',
  // Unix
  'ls', 'cat', 'head', 'tail', 'grep', 'find', 'cp', 'mv',
  'pwd', 'cd', 'touch', 'chmod', 'which', 'env',
];

// Blocked substrings anywhere in command
export const BLOCKED_SUBSTRINGS: string[] = [
  'format', 'shutdown', 'reg ', 'diskpart', 'net user',
  'Add-MpPreference', 'Set-MpPreference',
  'rm -rf /', 'rm -rf ~', 'rm -rf /*',
  'mkfs', 'dd if=', ':(){', 'fork bomb',
  '> /dev/sda', '| sh', '| bash',
  'curl | sh', 'wget | sh',
  'sudo rm', 'sudo dd',
];

// Destructive commands requiring confirmation
export const DESTRUCTIVE_COMMANDS: string[] = [
  'del', 'rmdir', 'rm', 'remove-item',
  'git push', 'git reset --hard', 'git clean',
  'drop table', 'truncate', 'delete from',
];

// Confirmation TTL in milliseconds (10 minutes)
export const CONFIRMATION_TTL_MS = 10 * 60 * 1000;

// Max file size for undo storage (200KB)
export const MAX_UNDO_FILE_SIZE = 200 * 1024;

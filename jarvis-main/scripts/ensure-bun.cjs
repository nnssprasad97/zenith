#!/usr/bin/env node
const { execSync } = require('child_process');
try {
  execSync('bun --version', { stdio: 'ignore' });
} catch {
  console.log('Bun runtime not found. Installing...');
  execSync('curl -fsSL https://bun.sh/install | bash', { stdio: 'inherit' });
}

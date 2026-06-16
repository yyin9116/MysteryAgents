const { spawn } = require('node:child_process');
const { resolve } = require('node:path');

const rawArgs = process.argv.slice(2);
const filteredArgs = [];

for (let i = 0; i < rawArgs.length; i += 1) {
    const arg = rawArgs[i];
    if (arg.startsWith('--coveragePathIgnorePatterns')) {
        if (arg === '--coveragePathIgnorePatterns') {
            i += 1;
        }
        continue;
    }
    filteredArgs.push(arg);
}

const vitestBin = resolve(__dirname, '../node_modules/vitest/vitest.mjs');
const child = spawn(process.execPath, [vitestBin, 'run', ...filteredArgs], {
    stdio: 'inherit',
});

child.on('exit', (code) => {
    process.exit(code ?? 1);
});

child.on('error', (error) => {
    console.error(error);
    process.exit(1);
});

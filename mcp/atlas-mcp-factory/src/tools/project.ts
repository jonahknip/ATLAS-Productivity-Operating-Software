/**
 * Project Initialization Tools
 */

import { writeFile, mkdir } from 'fs/promises';
import { existsSync } from 'fs';
import { join } from 'path';
import { z } from 'zod';
import { ProjectInitSchema } from './schemas.js';

export interface ToolResult {
  success: boolean;
  data?: unknown;
  error?: string;
}

// Project templates
const TEMPLATES = {
  basic: {
    files: {
      'README.md': (name: string) => `# ${name}\n\nA new project.\n`,
      'package.json': (name: string, ts: boolean) => JSON.stringify({
        name: name.toLowerCase().replace(/\s+/g, '-'),
        version: '1.0.0',
        main: ts ? 'dist/index.js' : 'src/index.js',
        scripts: {
          build: ts ? 'tsc' : 'echo "No build step"',
          start: ts ? 'node dist/index.js' : 'node src/index.js',
          dev: ts ? 'tsx watch src/index.ts' : 'node src/index.js',
        },
      }, null, 2),
      'src/index.ts': () => 'console.log("Hello, World!");\n',
    },
    dirs: ['src'],
  },
  webapp: {
    files: {
      'README.md': (name: string) => `# ${name}\n\nA web application.\n`,
      'package.json': (name: string, ts: boolean) => JSON.stringify({
        name: name.toLowerCase().replace(/\s+/g, '-'),
        version: '1.0.0',
        type: 'module',
        scripts: {
          dev: 'vite',
          build: 'vite build',
          preview: 'vite preview',
        },
        dependencies: {
          react: '^18.2.0',
          'react-dom': '^18.2.0',
        },
        devDependencies: {
          vite: '^5.0.0',
          '@vitejs/plugin-react': '^4.0.0',
          ...(ts ? { typescript: '^5.0.0', '@types/react': '^18.0.0', '@types/react-dom': '^18.0.0' } : {}),
        },
      }, null, 2),
      'index.html': (name: string) => `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>${name}</title>
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/main.tsx"></script>
</body>
</html>`,
      'src/main.tsx': () => `import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);`,
      'src/App.tsx': (name: string) => `export default function App() {
  return (
    <div>
      <h1>${name}</h1>
      <p>Welcome to your new app!</p>
    </div>
  );
}`,
    },
    dirs: ['src', 'public'],
  },
  api: {
    files: {
      'README.md': (name: string) => `# ${name}\n\nAn API server.\n`,
      'package.json': (name: string, ts: boolean) => JSON.stringify({
        name: name.toLowerCase().replace(/\s+/g, '-'),
        version: '1.0.0',
        type: 'module',
        scripts: {
          dev: ts ? 'tsx watch src/index.ts' : 'node --watch src/index.js',
          build: ts ? 'tsc' : 'echo "No build"',
          start: ts ? 'node dist/index.js' : 'node src/index.js',
        },
        dependencies: {
          express: '^4.18.0',
          cors: '^2.8.0',
        },
        devDependencies: ts ? {
          typescript: '^5.0.0',
          tsx: '^4.0.0',
          '@types/node': '^20.0.0',
          '@types/express': '^4.17.0',
          '@types/cors': '^2.8.0',
        } : {},
      }, null, 2),
      'src/index.ts': () => `import express from 'express';
import cors from 'cors';

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

app.get('/health', (_req, res) => {
  res.json({ status: 'healthy' });
});

app.listen(PORT, () => {
  console.log(\`Server running on port \${PORT}\`);
});`,
    },
    dirs: ['src'],
  },
  cli: {
    files: {
      'README.md': (name: string) => `# ${name}\n\nA command-line tool.\n`,
      'package.json': (name: string, ts: boolean) => JSON.stringify({
        name: name.toLowerCase().replace(/\s+/g, '-'),
        version: '1.0.0',
        type: 'module',
        bin: {
          [name.toLowerCase()]: ts ? './dist/cli.js' : './src/cli.js',
        },
        scripts: {
          build: ts ? 'tsc' : 'echo "No build"',
          start: ts ? 'node dist/cli.js' : 'node src/cli.js',
        },
        dependencies: {
          commander: '^12.0.0',
        },
        devDependencies: ts ? { typescript: '^5.0.0', '@types/node': '^20.0.0' } : {},
      }, null, 2),
      'src/cli.ts': (name: string) => `#!/usr/bin/env node
import { Command } from 'commander';

const program = new Command();

program
  .name('${name.toLowerCase()}')
  .version('1.0.0')
  .description('${name} CLI');

program
  .command('hello')
  .description('Say hello')
  .action(() => {
    console.log('Hello from ${name}!');
  });

program.parse();`,
    },
    dirs: ['src'],
  },
  monorepo: {
    files: {
      'README.md': (name: string) => `# ${name}\n\nA monorepo workspace.\n`,
      'package.json': (name: string) => JSON.stringify({
        name: name.toLowerCase().replace(/\s+/g, '-'),
        private: true,
        workspaces: ['packages/*', 'apps/*'],
        scripts: {
          build: 'turbo build',
          dev: 'turbo dev',
          test: 'turbo test',
        },
        devDependencies: {
          turbo: '^2.0.0',
        },
      }, null, 2),
      'turbo.json': () => JSON.stringify({
        $schema: 'https://turbo.build/schema.json',
        tasks: {
          build: { dependsOn: ['^build'], outputs: ['dist/**'] },
          dev: { cache: false, persistent: true },
          test: {},
        },
      }, null, 2),
    },
    dirs: ['packages', 'apps'],
  },
};

export async function projectInit(args: z.infer<typeof ProjectInitSchema>): Promise<ToolResult> {
  const parsed = ProjectInitSchema.parse(args);
  const projectDir = join(parsed.output_dir, parsed.name);
  
  // Check if directory exists
  if (existsSync(projectDir)) {
    return { success: false, error: `Directory already exists: ${projectDir}` };
  }
  
  const template = TEMPLATES[parsed.template];
  if (!template) {
    return { success: false, error: `Unknown template: ${parsed.template}` };
  }
  
  try {
    // Create project directory
    await mkdir(projectDir, { recursive: true });
    
    // Create subdirectories
    for (const dir of template.dirs) {
      await mkdir(join(projectDir, dir), { recursive: true });
    }
    
    // Create files
    const createdFiles: string[] = [];
    for (const [path, generator] of Object.entries(template.files)) {
      const content = typeof generator === 'function' 
        ? generator(parsed.name, parsed.options.typescript)
        : generator;
      await writeFile(join(projectDir, path), content);
      createdFiles.push(path);
    }
    
    // Add TypeScript config if enabled
    if (parsed.options.typescript && parsed.template !== 'monorepo') {
      const tsconfig = JSON.stringify({
        compilerOptions: {
          target: 'ES2022',
          module: 'NodeNext',
          moduleResolution: 'NodeNext',
          outDir: './dist',
          rootDir: './src',
          strict: true,
          esModuleInterop: true,
          skipLibCheck: true,
        },
        include: ['src/**/*'],
        exclude: ['node_modules', 'dist'],
      }, null, 2);
      await writeFile(join(projectDir, 'tsconfig.json'), tsconfig);
      createdFiles.push('tsconfig.json');
    }
    
    // Add .gitignore if git enabled
    if (parsed.options.git) {
      const gitignore = `node_modules/
dist/
.env
.env.local
*.log
.DS_Store
`;
      await writeFile(join(projectDir, '.gitignore'), gitignore);
      createdFiles.push('.gitignore');
    }
    
    // Add Dockerfile if docker enabled
    if (parsed.options.docker) {
      const dockerfile = `FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
CMD ["npm", "start"]
`;
      await writeFile(join(projectDir, 'Dockerfile'), dockerfile);
      createdFiles.push('Dockerfile');
    }
    
    return {
      success: true,
      data: {
        project_dir: projectDir,
        template: parsed.template,
        files_created: createdFiles,
        options: parsed.options,
      },
    };
  } catch (err) {
    return { success: false, error: String(err) };
  }
}

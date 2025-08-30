
import tsParser from './gui/node_modules/@typescript-eslint/parser/dist/index.js';

export default [
  {
    files: ['gui/src/**/*.{ts,tsx}'],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        project: './gui/tsconfig.json',
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {},
  },

export default [
  {
    ignores: [
      'gui/**',
      'capsule_brain/gui/static/**',
      'LIQUID-HIVE-main/**',
      'node_modules/**'
    ]
  }
];

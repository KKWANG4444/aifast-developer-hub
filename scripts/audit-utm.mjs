#!/usr/bin/env node

import { readFile, readdir } from 'node:fs/promises';
import { resolve, relative, basename, extname } from 'node:path';

const ALLOWED = {
  utm_source: new Set(['github', 'csdn', 'zhihu', 'juejin', 'nodeseek', 'devto']),
  utm_medium: new Set(['profile', 'repository', 'article', 'answer', 'release', 'third-party', 'pages']),
  utm_campaign: new Set(['developer_acquisition', 'integration-guide', 'api-doctor', 'model-check']),
};
const REQUIRED = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content'];
const TEXT_EXTENSIONS = new Set(['.md', '.html', '.htm', '.txt', '.json', '.yml', '.yaml']);
const SKIP_DIRECTORIES = new Set(['.git', 'node_modules', '_site', 'dist', 'coverage']);
const MACHINE_READABLE = new Set(['llms.txt', 'llms-full.txt', 'brand-facts.json']);
const URL_PATTERN = /https?:\/\/[^\s<>'"`)\]]+/g;

async function collectFiles(path) {
  const entries = await readdir(path, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    if (entry.isDirectory() && SKIP_DIRECTORIES.has(entry.name)) continue;
    const fullPath = resolve(path, entry.name);
    if (entry.isDirectory()) files.push(...await collectFiles(fullPath));
    if (entry.isFile() && TEXT_EXTENSIONS.has(extname(entry.name))) files.push(fullPath);
  }
  return files;
}

function cleanUrl(raw) {
  return raw.replace(/[.,;:!?]+$/, '').replace(/&amp;/g, '&');
}

function inspectUrl(raw, file, line) {
  const errors = [];
  const cleaned = cleanUrl(raw);
  let url;
  try {
    url = new URL(cleaned);
  } catch {
    return errors;
  }

  const utmKeys = [...url.searchParams.keys()].filter((key) => key.startsWith('utm_'));
  if (utmKeys.length === 0) return errors;

  if (MACHINE_READABLE.has(basename(file))) {
    errors.push(`${line}: 机器可读文件不得包含 UTM：${cleaned}`);
  }

  if (url.hostname === 'www.aifast.club' && (url.pathname === '/v1' || url.pathname.startsWith('/v1/') || url.pathname === '/models')) {
    errors.push(`${line}: API 调用地址不得包含 UTM：${cleaned}`);
  }

  for (const key of REQUIRED) {
    if (!url.searchParams.get(key)) errors.push(`${line}: 追踪链接缺少 ${key}：${cleaned}`);
  }

  for (const [key, allowedValues] of Object.entries(ALLOWED)) {
    const value = url.searchParams.get(key);
    if (value && !allowedValues.has(value)) {
      errors.push(`${line}: ${key} 使用未知值 ${value}：${cleaned}`);
    }
  }

  const content = url.searchParams.get('utm_content');
  if (content && !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(content)) {
    errors.push(`${line}: utm_content 必须使用小写字母、数字和短横线：${cleaned}`);
  }

  return errors;
}

async function auditRoot(root) {
  const files = await collectFiles(root);
  const findings = [];
  const contentSlots = [];
  let trackedUrls = 0;

  for (const file of files) {
    const content = await readFile(file, 'utf8');
    const lines = content.split(/\r?\n/);
    lines.forEach((line, index) => {
      const urls = line.match(URL_PATTERN) ?? [];
      for (const url of urls) {
        if (url.includes('utm_')) {
          trackedUrls += 1;
          try {
            const parsed = new URL(cleanUrl(url));
            const content = parsed.searchParams.get('utm_content');
            if (content) contentSlots.push({ content, file, line: index + 1 });
          } catch {
            // URL 结构问题由 inspectUrl 统一报告。
          }
        }
        for (const error of inspectUrl(url, file, index + 1)) {
          findings.push(`${relative(root, file)}:${error}`);
        }
      }
    });
  }

  return { root, files: files.length, trackedUrls, findings, contentSlots };
}

const roots = (process.argv.slice(2).length ? process.argv.slice(2) : ['.']).map((path) => resolve(path));
let failed = false;
const allContentSlots = new Map();

for (const root of roots) {
  const result = await auditRoot(root);
  console.log(`${result.root}: ${result.files} 个文本文件，${result.trackedUrls} 个 UTM 链接`);
  if (result.findings.length === 0) {
    console.log('  通过');
  } else {
    failed = true;
    for (const finding of result.findings) console.error(`  ${finding}`);
  }

  for (const slot of result.contentSlots) {
    const locations = allContentSlots.get(slot.content) ?? [];
    locations.push(`${relative(process.cwd(), slot.file)}:${slot.line}`);
    allContentSlots.set(slot.content, locations);
  }
}

for (const [content, locations] of allContentSlots) {
  if (locations.length < 2) continue;
  failed = true;
  console.error(`重复 utm_content=${content}`);
  for (const location of locations) console.error(`  ${location}`);
}

if (failed) process.exitCode = 1;

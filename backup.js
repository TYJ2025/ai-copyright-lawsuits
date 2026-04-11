#!/usr/bin/env node
/**
 * AI Copyright Lawsuits Dashboard — Backup Tool
 * ──────────────────────────────────────────────
 * Usage:
 *   node backup.js export              # 匯出 → dashboard-backup-YYYY-MM-DD.json (Base64)
 *   node backup.js export --plain      # 匯出 → 不做 Base64，直接 JSON
 *   node backup.js import <file>       # 匯入並合併（不覆蓋既有案件，僅新增/更新 progress）
 *   node backup.js import <file> --overwrite  # 匯入並完全覆蓋
 *
 * 所有資料從 dashboard.html 同目錄讀取/寫入。
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const DASHBOARD = path.join(__dirname, 'dashboard.html');

// ─── Helpers ───

function readDashboard() {
  if (!fs.existsSync(DASHBOARD)) {
    console.error('❌ 找不到 dashboard.html：' + DASHBOARD);
    process.exit(1);
  }
  return fs.readFileSync(DASHBOARD, 'utf-8');
}

/**
 * Extract a JS variable block from the HTML.
 * Handles: const NAME = [ ... ]; or const NAME = { ... };
 * Uses bracket counting to find the matching close.
 */
function extractJSBlock(html, varName) {
  const re = new RegExp(`const ${varName}\\s*=\\s*`);
  const match = re.exec(html);
  if (!match) return null;

  const startIdx = match.index + match[0].length;
  const openChar = html[startIdx]; // '[' or '{'
  const closeChar = openChar === '[' ? ']' : '}';

  let depth = 0;
  let inString = false;
  let stringChar = '';
  let escaped = false;
  let i = startIdx;

  for (; i < html.length; i++) {
    const ch = html[i];
    if (escaped) { escaped = false; continue; }
    if (ch === '\\' && inString) { escaped = true; continue; }

    if (inString) {
      if (ch === stringChar) inString = false;
      continue;
    }

    if (ch === '"' || ch === "'" || ch === '`') {
      inString = true;
      stringChar = ch;
      continue;
    }

    if (ch === openChar) depth++;
    if (ch === closeChar) {
      depth--;
      if (depth === 0) {
        return {
          raw: html.substring(match.index, i + 2), // include trailing ;
          body: html.substring(startIdx, i + 1),
          fullStart: match.index,
          fullEnd: i + 2, // past the ;
        };
      }
    }
  }
  return null;
}

/**
 * Safely evaluate a JS data literal (array or object) that uses
 * template literals and trailing commas — things JSON.parse can't handle.
 */
function evalBlock(bodyStr) {
  const sandbox = {};
  vm.runInNewContext(`__result = ${bodyStr}`, sandbox);
  return sandbox.__result;
}

// ─── Export ───

function doExport(plain) {
  const html = readDashboard();

  const blocks = {
    caseSources: extractJSBlock(html, 'caseSources'),
    cases: extractJSBlock(html, 'cases'),
    newsItems: extractJSBlock(html, 'newsItems'),
    fairUseCases: extractJSBlock(html, 'fairUseCases'),
    officialReports: extractJSBlock(html, 'officialReports'),
  };

  const data = {};
  for (const [key, block] of Object.entries(blocks)) {
    if (!block) {
      console.warn(`⚠️  找不到 ${key}，跳過`);
      continue;
    }
    try {
      data[key] = evalBlock(block.body);
    } catch (e) {
      console.warn(`⚠️  解析 ${key} 失敗：${e.message}，改用原始文字`);
      data[key] = block.body;
    }
  }

  // Metadata
  data._meta = {
    exportDate: new Date().toISOString(),
    caseCount: Array.isArray(data.cases) ? data.cases.length : '?',
    dashboardFile: DASHBOARD,
  };

  const jsonStr = JSON.stringify(data, null, 2);
  const today = new Date().toISOString().slice(0, 10);
  let outFile, outContent;

  if (plain) {
    outFile = path.join(__dirname, `dashboard-backup-${today}.json`);
    outContent = jsonStr;
  } else {
    outFile = path.join(__dirname, `dashboard-backup-${today}.b64.json`);
    outContent = Buffer.from(jsonStr, 'utf-8').toString('base64');
  }

  fs.writeFileSync(outFile, outContent, 'utf-8');
  console.log(`✅ 匯出完成：${outFile}`);
  console.log(`   案件數：${data._meta.caseCount}`);
  console.log(`   格式：${plain ? 'Plain JSON' : 'Base64 encoded'}`);
  console.log(`   檔案大小：${(fs.statSync(outFile).size / 1024).toFixed(1)} KB`);
}

// ─── Import (Merge) ───

function doImport(file, overwrite) {
  if (!fs.existsSync(file)) {
    console.error('❌ 找不到匯入檔案：' + file);
    process.exit(1);
  }

  // Read and decode
  let raw = fs.readFileSync(file, 'utf-8').trim();
  let imported;

  // Detect Base64 vs plain JSON
  if (raw.startsWith('{')) {
    imported = JSON.parse(raw);
  } else {
    const decoded = Buffer.from(raw, 'base64').toString('utf-8');
    imported = JSON.parse(decoded);
  }

  console.log(`📂 匯入檔案：${file}`);
  console.log(`   匯出日期：${imported._meta?.exportDate || '未知'}`);
  console.log(`   案件數：${imported._meta?.caseCount || '?'}`);
  console.log(`   模式：${overwrite ? '完全覆蓋' : '合併（預設）'}`);

  const html = readDashboard();

  // Backup current file first
  const backupPath = DASHBOARD + '.bak-' + new Date().toISOString().slice(0, 19).replace(/:/g, '');
  fs.writeFileSync(backupPath, html, 'utf-8');
  console.log(`💾 已備份現有 dashboard → ${path.basename(backupPath)}`);

  let updatedHtml = html;

  // Helper: replace a JS block in the HTML
  function replaceBlock(varName, newData) {
    const block = extractJSBlock(updatedHtml, varName);
    if (!block) {
      console.warn(`⚠️  dashboard.html 中找不到 ${varName}，跳過`);
      return;
    }
    const newBody = JSON.stringify(newData, null, 2)
      // Convert JSON strings with \n back to template literals for readability
      .replace(/"([^"]*\\n[^"]*)"/g, (match, inner) => {
        return '`' + inner.replace(/\\n/g, '\n').replace(/\\"/g, '"') + '`';
      });

    const declaration = `const ${varName} = ${newBody};`;
    updatedHtml = updatedHtml.substring(0, block.fullStart) + declaration + updatedHtml.substring(block.fullEnd);
  }

  if (overwrite) {
    // ── Overwrite mode: replace all blocks ──
    for (const key of ['caseSources', 'cases', 'newsItems', 'fairUseCases', 'officialReports']) {
      if (imported[key]) {
        replaceBlock(key, imported[key]);
        console.log(`   🔄 ${key} — 已覆蓋`);
      }
    }
  } else {
    // ── Merge mode ──

    // 1. Merge cases: add new, update progress of existing
    if (imported.cases && Array.isArray(imported.cases)) {
      const currentBlock = extractJSBlock(updatedHtml, 'cases');
      if (currentBlock) {
        const currentCases = evalBlock(currentBlock.body);
        const currentIds = new Set(currentCases.map(c => c.id));
        let added = 0, updated = 0;

        for (const ic of imported.cases) {
          const existing = currentCases.find(c => c.id === ic.id);
          if (!existing) {
            currentCases.push(ic);
            added++;
          } else {
            // Update progress if imported has newer content
            if (ic.progress && ic.progress !== existing.progress) {
              existing.progress = ic.progress;
              updated++;
            }
          }
        }

        // Sort by id
        currentCases.sort((a, b) => a.id - b.id);
        replaceBlock('cases', currentCases);
        console.log(`   📋 cases — 新增 ${added}，更新 ${updated}`);
      }
    }

    // 2. Merge caseSources: add new entries
    if (imported.caseSources && typeof imported.caseSources === 'object') {
      const currentBlock = extractJSBlock(updatedHtml, 'caseSources');
      if (currentBlock) {
        const currentSources = evalBlock(currentBlock.body);
        let added = 0;
        for (const [id, sources] of Object.entries(imported.caseSources)) {
          if (!currentSources[id]) {
            currentSources[id] = sources;
            added++;
          }
        }
        replaceBlock('caseSources', currentSources);
        console.log(`   🔗 caseSources — 新增 ${added} 筆`);
      }
    }

    // 3. newsItems: always replace with imported (latest wins)
    if (imported.newsItems) {
      replaceBlock('newsItems', imported.newsItems);
      console.log(`   📰 newsItems — 已更新`);
    }

    // 4. fairUseCases: add new entries by id
    if (imported.fairUseCases && Array.isArray(imported.fairUseCases)) {
      const currentBlock = extractJSBlock(updatedHtml, 'fairUseCases');
      if (currentBlock) {
        const current = evalBlock(currentBlock.body);
        const currentIds = new Set(current.map(c => c.id));
        let added = 0;
        for (const fc of imported.fairUseCases) {
          if (!currentIds.has(fc.id)) {
            current.push(fc);
            added++;
          }
        }
        replaceBlock('fairUseCases', current);
        console.log(`   ⚖️  fairUseCases — 新增 ${added}`);
      }
    }

    // 5. officialReports: replace entirely (hard to diff-merge nested structure)
    if (imported.officialReports) {
      replaceBlock('officialReports', imported.officialReports);
      console.log(`   🏛️  officialReports — 已更新`);
    }
  }

  fs.writeFileSync(DASHBOARD, updatedHtml, 'utf-8');
  console.log(`\n✅ 匯入完成！dashboard.html 已更新。`);
}

// ─── CLI ───

const args = process.argv.slice(2);
const cmd = args[0];

if (cmd === 'export') {
  const plain = args.includes('--plain');
  doExport(plain);
} else if (cmd === 'import' && args[1]) {
  const file = path.resolve(args[1]);
  const overwrite = args.includes('--overwrite');
  doImport(file, overwrite);
} else {
  console.log(`
📦 AI Copyright Dashboard Backup Tool
──────────────────────────────────────
用法：
  node backup.js export              匯出為 Base64 JSON 備份檔
  node backup.js export --plain      匯出為明文 JSON（方便閱讀）
  node backup.js import <file>       匯入並合併（新案件新增，既有案件更新 progress）
  node backup.js import <file> --overwrite  匯入並完全覆蓋所有資料

合併模式說明：
  • cases：依 ID 比對，新 ID 新增，既有 ID 僅更新 progress 欄位
  • caseSources：新 ID 新增，既有不動
  • newsItems：整批替換為匯入版本
  • fairUseCases：依 ID 新增
  • officialReports：整批替換

匯入前會自動建立 dashboard.html.bak-* 備份。
  `);
}

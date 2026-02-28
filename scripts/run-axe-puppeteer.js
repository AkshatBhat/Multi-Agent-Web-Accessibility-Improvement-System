#!/usr/bin/env node
const fs        = require('fs');
const path      = require('path');
const puppeteer = require('puppeteer');
const { AxePuppeteer } = require('axe-puppeteer');

const EXAMPLE_FAILURE_LOG = '/Users/akshat/Data/UIUC/Spring 2025/Courses/CS 568 User-Centered Machine Learning/Project/WebUI-7k/axe_failures.txt';

(async () => {
  const [, , jobsFile, failureLogArg] = process.argv;
  if (!jobsFile) {
    console.error('Usage: node run-axe-puppeteer.js <axe_jobs.json> [failure_log_path]');
    console.error(`Example failure log path: ${EXAMPLE_FAILURE_LOG}`);
    process.exit(1);
  }
  const failureLog = failureLogArg || process.env.AXE_FAILURE_LOG || path.join(process.cwd(), 'axe_failures.txt');

  // clear out old failure log
  try {
    fs.writeFileSync(failureLog, '');
  } catch {
    // ignore
  }

  let jobs;
  try {
    jobs = JSON.parse(fs.readFileSync(jobsFile, 'utf-8'));
  } catch (err) {
    console.error('❌ Failed to read jobs file:', err.message);
    process.exit(1);
  }

  const browser = await puppeteer.launch({
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
    headless: true,
  });
  const page = await browser.newPage();

  await page.setRequestInterception(true);
  page.on('request', req => {
    const t = req.resourceType();
    if (['image','media','font','stylesheet'].includes(t)) req.abort();
    else req.continue();
  });

  for (const { htmlUrl, outFile, pageId, vpIndex } of jobs) {
    console.log(`→ [${pageId}@${vpIndex}] ⏳ loading ${htmlUrl}`);
    try {
      await page.goto(htmlUrl, {
        waitUntil: 'networkidle2',
        timeout: 30000,
      });

      console.log(`→ [${pageId}@${vpIndex}] 🪝 running axe`);
      const results = await new AxePuppeteer(page)
        .include('body')
        .analyze();

      fs.writeFileSync(outFile, JSON.stringify(results, null, 2));
      console.log(`→ [${pageId}@${vpIndex}] ✅ done`);
    } catch (err) {
      console.error(`⚠️  Axe failed for ${pageId}@${vpIndex}:`, err.message);
      const stub = { error: err.message, violations: [] };
      try {
        fs.writeFileSync(outFile, JSON.stringify(stub, null, 2));
      } catch (writeErr) {
        console.error(`❌ Could not write stub for ${pageId}@${vpIndex}:`, writeErr.message);
      }
      try {
        fs.appendFileSync(
          failureLog,
          `${pageId}@${vpIndex}\t${htmlUrl}\t${err.message}\n`
        );
      } catch (logErr) {
        console.error(`❌ Could not log failure for ${pageId}@${vpIndex}:`, logErr.message);
      }
    }
  }

  await browser.close();
  console.log('🏁 All Axe jobs complete.');
})();

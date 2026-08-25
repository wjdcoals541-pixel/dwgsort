const path = require('path');
const fs = require('fs');
const { pathToFileURL } = require('url');
const { chromium } = require('playwright');
const sharp = require('sharp');

const root = path.resolve(__dirname, '..', '..');
const outputDir = path.join(root, 'output', 'pdf');
const previewDir = path.join(root, 'tmp', 'pdfs', 'portfolio-preview');
const pdfPath = path.join(outputDir, '정채민_엔지니어_포트폴리오_수정본.pdf');
const contactSheetPath = path.join(previewDir, '정채민_엔지니어_포트폴리오_미리보기.png');
const chromePath = process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

fs.mkdirSync(outputDir, { recursive: true });
fs.mkdirSync(previewDir, { recursive: true });

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: chromePath });
  const context = await browser.newContext({ viewport: { width: 1200, height: 1300 }, deviceScaleFactor: 1.5 });
  const page = await context.newPage();
  await page.goto(pathToFileURL(path.join(__dirname, 'index.html')).href, { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);

  const sheets = page.locator('.sheet');
  const count = await sheets.count();
  const previewPaths = [];

  for (let i = 0; i < count; i += 1) {
    const previewPath = path.join(previewDir, `page-${String(i + 1).padStart(2, '0')}.png`);
    await sheets.nth(i).screenshot({ path: previewPath });
    previewPaths.push(previewPath);
  }

  await page.pdf({
    path: pdfPath,
    format: 'A4',
    printBackground: true,
    preferCSSPageSize: true,
    margin: { top: 0, right: 0, bottom: 0, left: 0 },
  });

  const thumbWidth = 330;
  const thumbHeight = 467;
  const gap = 24;
  const columns = 4;
  const rows = Math.ceil(count / columns);
  const canvasWidth = columns * thumbWidth + (columns + 1) * gap;
  const canvasHeight = rows * thumbHeight + (rows + 1) * gap;
  const composites = [];

  for (let i = 0; i < previewPaths.length; i += 1) {
    const buffer = await sharp(previewPaths[i]).resize(thumbWidth, thumbHeight, { fit: 'fill' }).png().toBuffer();
    composites.push({
      input: buffer,
      left: gap + (i % columns) * (thumbWidth + gap),
      top: gap + Math.floor(i / columns) * (thumbHeight + gap),
    });
  }

  await sharp({
    create: { width: canvasWidth, height: canvasHeight, channels: 4, background: '#dde2e4' },
  }).composite(composites).png().toFile(contactSheetPath);

  const overflows = await page.evaluate(() => [...document.querySelectorAll('.sheet')].map((sheet, index) => ({
    page: index + 1,
    scrollWidth: sheet.scrollWidth,
    clientWidth: sheet.clientWidth,
    scrollHeight: sheet.scrollHeight,
    clientHeight: sheet.clientHeight,
    overflowX: sheet.scrollWidth > sheet.clientWidth,
    overflowY: sheet.scrollHeight > sheet.clientHeight,
  })));

  console.log(JSON.stringify({ pdfPath, contactSheetPath, pageCount: count, overflows }, null, 2));
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

'use strict';
// Development-only browser validation. No authentication to real services is involved.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {chromium} = require('playwright');

(async () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'agent-os-browser-'));
  const root = path.join(temp, 'AI_AGENT_OS_QA');
  fs.mkdirSync(root);
  const fixture = spawn('python3', ['-u', 'tests/browser_fixture.py', root]);
  fixture.stderr.on('data', value => process.stderr.write(value));
  let browser;
  try {
    const port = await new Promise((resolve, reject) => {
      let received = '';
      const timeout = setTimeout(() => reject(Error('Fixture startup timeout')), 15000);
      fixture.stdout.on('data', value => {
        received += value.toString();
        if(received.includes('\n')) {clearTimeout(timeout);resolve(JSON.parse(received.split('\n')[0]).port);}
      });
      fixture.once('error', reject);
      fixture.once('exit', code => {if(code)reject(Error('Fixture exited: '+code));});
    });
    const secret = fs.readFileSync(path.join(root, '.agent-os/dashboard.token'), 'utf8').trim();
    browser = await chromium.launch({headless:true});
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`http://127.0.0.1:${port}/#token=${secret}`);
    await page.locator('#app').waitFor({state:'visible'});
    assert.equal(new URL(page.url()).hash, '', 'Access fragment must be cleared');
    assert.equal(await page.locator('#model').inputValue(), 'gpt-5.6-luna');
    await page.locator('#goal-title').fill('Relatório semanal');
    await page.locator('#goal-description').fill('Criar um relatório com dados de exemplo e instruções no GitHub.');
    await page.locator('#goal-acceptance').fill('O arquivo existe e os totais conferem com os dados de exemplo.');
    await page.locator('#goal-form button[type=submit]').click();
    await page.locator('#goals h3').filter({hasText:'Relatório semanal'}).waitFor();
    await page.locator('#model').fill('gpt-6-astra');
    await page.locator('#reasoning').fill('high');
    await page.locator('#fast').check();
    await page.locator('#settings-form button[type=submit]').click();
    await page.waitForFunction(() => document.getElementById('notice').textContent.includes('Configuração salva'));
    await page.reload();
    await page.locator('#app').waitFor({state:'visible'});
    assert.equal(await page.locator('#model').inputValue(), 'gpt-6-astra');
    assert.equal(await page.locator('#fast').isChecked(), true);
    await page.locator('#pause').click();
    await page.waitForFunction(() => document.getElementById('pause').textContent === 'Retomar');
    await page.locator('#pause').click();
    await page.waitForFunction(() => document.getElementById('pause').textContent === 'Pausar');
    fs.mkdirSync('browser-artifacts', {recursive:true});
    await page.screenshot({path:'browser-artifacts/dashboard-desktop.png',fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'Mobile layout must not overflow');
    await page.screenshot({path:'browser-artifacts/dashboard-mobile.png',fullPage:true});
    await page.getByRole('button',{name:'Cancelar',exact:true}).click();
    await page.locator('#goals .badge').filter({hasText:'Cancelado'}).waitFor();
    await page.locator('#goal-title').fill('<img src=x onerror=alert(1)>');
    await page.locator('#goal-description').fill('Render this as text.');
    await page.locator('#goal-acceptance').fill('No injected HTML nodes.');
    await page.locator('#goal-form button[type=submit]').click();
    await page.locator('#goals h3').filter({hasText:'<img src=x onerror=alert(1)>'}).waitFor();
    assert.equal(await page.locator('#goals img').count(), 0);
    assert.deepEqual(errors, []);
    fs.writeFileSync('browser-artifacts/result.json', JSON.stringify({passed:true,checks:['authentication fragment removal','goal submission','model and Fast persistence','pause and resume','cancellation','mobile overflow','HTML injection prevention','no page JavaScript errors']},null,2));
    console.log('Browser workflow passed: desktop, mobile, goals, settings, controls and text rendering.');
  } finally {
    if(browser)await browser.close();
    fixture.kill('SIGTERM');
    await new Promise(resolve => {if(fixture.exitCode !== null)resolve();else fixture.once('exit',resolve);});
    fs.rmSync(temp,{recursive:true,force:true});
  }
})().catch(error => {console.error(error);process.exitCode=1;});

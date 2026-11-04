// Serve this repository locally, then run with Node and Playwright.
// TEST_URL, PLAYWRIGHT_MODULE and BROWSER_EXECUTABLE may override defaults.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict'),fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.BROWSER_EXECUTABLE||undefined,headless:true});let failed=0;const results=[];
 async function check(name,repo,fn,init){const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];page.setDefaultTimeout(6000);page.on('pageerror',e=>errors.push(e.message));try{if(init)await page.addInitScript(init);await page.goto(process.env.TEST_URL||'http://127.0.0.1:8000/',{waitUntil:'domcontentloaded'});await fn(page);assert.deepEqual(errors,[]);results.push({name,passed:true});console.log('PASS',name);}catch(e){failed++;results.push({name,passed:false,error:e.message,errors});console.log('FAIL',name,e.message,errors)}finally{await page.close()}}

 await check('webgame new arcade searchable and counts correct','webgame',async p=>{await p.locator('nav [data-page=games]').click();assert.equal(await p.locator('#game-list .game').count(),11);await p.locator('#search').fill('guras1984');assert.equal(await p.locator('#game-list .game:visible').count(),1);assert.match(await p.locator('#game-list .game:visible a.play').getAttribute('href'),/GURAS1984game/)});
 await browser.close();process.exitCode=failed?1:0;
})();

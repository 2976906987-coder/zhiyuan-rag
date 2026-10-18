const {JSDOM} = require('jsdom');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const dom = new JSDOM('<div id="answer"></div>', {runScripts: 'outside-only'});
for (const file of ['vendor/marked.umd.js', 'vendor/purify.min.js', 'markdown.js']) {
    dom.window.eval(fs.readFileSync(`app/static/${file}`, 'utf8'));
}
dom.window.renderAnswer('默认 **8080**，使用 `PORT`。[1]\n\n- 第一项\n- 第二项\n\n```python\nprint(1)\n```\n\n| 名称 | 值 |\n|---|---|\n|端口|8080|');
const answer = dom.window.document.getElementById('answer');
assert.equal(answer.querySelector('strong').textContent, '8080');
assert.equal(answer.querySelector('code').textContent, 'PORT');
assert.equal(answer.querySelectorAll('li').length, 2);
assert.ok(answer.querySelector('pre code'));
assert.ok(answer.querySelector('table'));
assert.ok(answer.textContent.includes('[1]'));
dom.window.renderAnswer('<script>alert(1)</script><img src=x onerror=alert(1)><a href="javascript:alert(1)">bad</a><svg onload=alert(1)></svg>');
assert.equal(answer.querySelectorAll('script,img,svg,[onerror],[onload]').length, 0);
assert.equal(answer.querySelector('a').getAttribute('href'), null);
dom.window.renderAnswer('**生成中的');
dom.window.renderAnswer('**生成中的文字**');
assert.equal(answer.querySelector('strong').textContent, '生成中的文字');
console.log('PASS: Markdown formatting, citations, streaming updates, HTML filtering');

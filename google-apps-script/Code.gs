// ═══════════════════════════════════════════════════════════════
//  Rukphong Personal Dashboard — Google Apps Script Backend
//  Handles: CRUD for all data types + LINE Webhook
// ═══════════════════════════════════════════════════════════════
//
//  SETUP (Script Properties → Project Settings → Script Properties):
//    SPREADSHEET_ID  → ID of your Google Sheet (from the URL)
//    LINE_TOKEN      → LINE Channel Access Token
//
//  DEPLOY:
//    Extensions → Apps Script → Deploy → New Deployment
//    Type: Web App | Execute as: Me | Who has access: Anyone
// ═══════════════════════════════════════════════════════════════

const P = PropertiesService.getScriptProperties();

function getSS() {
  return SpreadsheetApp.openById(P.getProperty('SPREADSHEET_ID'));
}

// ── Sheet & Header Definitions ────────────────────────────────

const SH = {
  expense:    'รายจ่าย',
  task:       'งาน',
  note:       'บันทึก',
  portfolio:  'Portfolio',
  investment: 'การลงทุน',
  dividend:   'เงินปันผล',
};

const HDR = {
  expense:    ['ID','วันที่','จำนวน','หมวดหมู่','วิธีชำระ','หมายเหตุ'],
  task:       ['ID','วันที่','ชื่องาน','Priority','Status','Due','หมายเหตุ'],
  note:       ['ID','วันที่','หัวข้อ','เนื้อหา','หมวดหมู่'],
  portfolio:  ['ID','ชื่อ','วันที่สร้าง'],
  investment: ['ID','PortfolioID','ประเภท','Symbol','ชื่อ','จำนวน','ราคาทุน','ราคาตลาด','หมายเหตุ'],
  dividend:   ['ID','PortfolioID','วันที่','จำนวนเงิน','Symbol','ประเภท','หมายเหตุ'],
};

const FIELDS = {
  expense:    ['id','date','amount','category','payment','notes'],
  task:       ['id','date','title','priority','status','due','notes'],
  note:       ['id','date','title','content','category'],
  portfolio:  ['id','name','created_at'],
  investment: ['id','portfolio_id','type','symbol','name','qty','cost_price','current_price','note'],
  dividend:   ['id','portfolio_id','date','amount','symbol','type','note'],
};

// ── Utilities ─────────────────────────────────────────────────

function uid() { return String(Date.now()); }

function today() {
  return Utilities.formatDate(new Date(), 'Asia/Bangkok', 'yyyy-MM-dd');
}

function jsonResp(data) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}

function getOrCreate(name, headers) {
  const ss = getSS();
  let sh = ss.getSheetByName(name);
  if (!sh) {
    sh = ss.insertSheet(name);
    sh.appendRow(headers);
    sh.getRange(1, 1, 1, headers.length)
      .setFontWeight('bold')
      .setBackground('#1A2340')
      .setFontColor('#FFFFFF');
    sh.setFrozenRows(1);
  }
  return sh;
}

function sheetToObjects(sh, fields) {
  const data = sh.getDataRange().getValues();
  if (data.length <= 1) return [];
  return data.slice(1)
    .filter(row => row[0] !== '' && row[0] !== undefined)
    .map(row => {
      const obj = {};
      fields.forEach((f, i) => { obj[f] = row[i] !== undefined ? String(row[i]) : ''; });
      return obj;
    });
}

function deleteById(type, id) {
  const sh = getOrCreate(SH[type], HDR[type]);
  const data = sh.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]) === String(id)) {
      sh.deleteRow(i + 1);
      return true;
    }
  }
  return false;
}

// ── HTTP: GET ─────────────────────────────────────────────────

function doGet(e) {
  const action = (e.parameter.action || '').toLowerCase();
  try {
    let data;
    switch (action) {
      case 'expenses':    data = getExpenses();   break;
      case 'tasks':       data = getTasks();      break;
      case 'notes':       data = getNotes();      break;
      case 'portfolios':  data = getPortfolios(); break;
      case 'investments': data = getInvestments(e.parameter.portfolio || ''); break;
      case 'dividends':   data = getDividends(e.parameter.portfolio || '');   break;
      default: return jsonResp({ ok: true, message: 'Rukphong Dashboard API v1 🚀' });
    }
    return jsonResp({ ok: true, data });
  } catch (err) {
    return jsonResp({ ok: false, error: err.toString() });
  }
}

// ── HTTP: POST ────────────────────────────────────────────────

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents);

    // LINE Webhook
    if (body.events !== undefined) {
      processLine(body.events);
      return ContentService.createTextOutput(JSON.stringify({ ok: true }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    // API Write
    const { action, record } = body;
    let result = { ok: false, error: 'Unknown action: ' + action };

    switch (action) {
      // Expense
      case 'saveExpense':   result = saveExpense(record);   break;
      case 'deleteExpense': deleteById('expense', record.id); result = { ok: true }; break;
      // Task
      case 'saveTask':      result = saveTask(record);     break;
      case 'deleteTask':    deleteById('task', record.id); result = { ok: true };   break;
      // Note
      case 'saveNote':      result = saveNote(record);     break;
      case 'deleteNote':    deleteById('note', record.id); result = { ok: true };   break;
      // Portfolio
      case 'savePortfolio':   result = savePortfolio(record);   break;
      case 'deletePortfolio': deletePortfolioAll(record.id); result = { ok: true }; break;
      // Investment
      case 'saveInvestment':   result = saveInvestment(record);   break;
      case 'deleteInvestment': deleteById('investment', record.id); result = { ok: true }; break;
      // Dividend
      case 'saveDividend':   result = saveDividend(record);   break;
      case 'deleteDividend': deleteById('dividend', record.id); result = { ok: true }; break;
    }
    return jsonResp(result);
  } catch (err) {
    return jsonResp({ ok: false, error: err.toString() });
  }
}

// ── EXPENSES ──────────────────────────────────────────────────

function getExpenses() {
  return sheetToObjects(getOrCreate(SH.expense, HDR.expense), FIELDS.expense);
}

function saveExpense(r) {
  if (r.id) deleteById('expense', r.id);
  const sh = getOrCreate(SH.expense, HDR.expense);
  const id = r.id || uid();
  sh.appendRow([id, r.date || today(), Number(r.amount) || 0,
    r.category || '', r.payment || '', r.notes || '']);
  return { ok: true, id };
}

// ── TASKS ─────────────────────────────────────────────────────

function getTasks() {
  return sheetToObjects(getOrCreate(SH.task, HDR.task), FIELDS.task);
}

function saveTask(r) {
  if (r.id) deleteById('task', r.id);
  const sh = getOrCreate(SH.task, HDR.task);
  const id = r.id || uid();
  sh.appendRow([id, r.date || today(), r.title || '',
    r.priority || 'medium', r.status || 'todo', r.due || '', r.notes || '']);
  return { ok: true, id };
}

// ── NOTES ─────────────────────────────────────────────────────

function getNotes() {
  return sheetToObjects(getOrCreate(SH.note, HDR.note), FIELDS.note);
}

function saveNote(r) {
  if (r.id) deleteById('note', r.id);
  const sh = getOrCreate(SH.note, HDR.note);
  const id = r.id || uid();
  sh.appendRow([id, r.date || today(), r.title || '', r.content || '', r.category || '']);
  return { ok: true, id };
}

// ── PORTFOLIOS ────────────────────────────────────────────────

function getPortfolios() {
  return sheetToObjects(getOrCreate(SH.portfolio, HDR.portfolio), FIELDS.portfolio);
}

function savePortfolio(r) {
  if (r.id) deleteById('portfolio', r.id);
  const sh = getOrCreate(SH.portfolio, HDR.portfolio);
  const id = r.id || uid();
  sh.appendRow([id, r.name || '', r.created_at || today()]);
  return { ok: true, id };
}

function deletePortfolioAll(pid) {
  deleteById('portfolio', pid);
  // Delete all related investments & dividends
  ['investment', 'dividend'].forEach(type => {
    const sh = getOrCreate(SH[type], HDR[type]);
    const data = sh.getDataRange().getValues();
    for (let i = data.length - 1; i >= 1; i--) {
      if (String(data[i][1]) === String(pid)) sh.deleteRow(i + 1);
    }
  });
}

// ── INVESTMENTS ───────────────────────────────────────────────

function getInvestments(portfolioId) {
  const all = sheetToObjects(getOrCreate(SH.investment, HDR.investment), FIELDS.investment);
  return portfolioId ? all.filter(r => r.portfolio_id === portfolioId) : all;
}

function saveInvestment(r) {
  if (r.id) deleteById('investment', r.id);
  const sh = getOrCreate(SH.investment, HDR.investment);
  const id = r.id || uid();
  sh.appendRow([id, r.portfolio_id || '', r.type || '', r.symbol || '',
    r.name || '', Number(r.qty) || 0, Number(r.cost_price || r.cost) || 0,
    Number(r.current_price || r.price) || 0, r.note || '']);
  return { ok: true, id };
}

// ── DIVIDENDS ─────────────────────────────────────────────────

function getDividends(portfolioId) {
  const all = sheetToObjects(getOrCreate(SH.dividend, HDR.dividend), FIELDS.dividend);
  return portfolioId ? all.filter(r => r.portfolio_id === portfolioId) : all;
}

function saveDividend(r) {
  if (r.id) deleteById('dividend', r.id);
  const sh = getOrCreate(SH.dividend, HDR.dividend);
  const id = r.id || uid();
  sh.appendRow([id, r.portfolio_id || '', r.date || today(),
    Number(r.amount) || 0, r.symbol || '', r.type || '', r.note || '']);
  return { ok: true, id };
}

// ── LINE WEBHOOK ──────────────────────────────────────────────

function processLine(events) {
  const token = P.getProperty('LINE_TOKEN');
  if (!token) return;

  for (const ev of events) {
    if (ev.type !== 'message' || ev.message.type !== 'text') continue;

    const text = ev.message.text.trim();
    const replyToken = ev.replyToken;
    let reply = '';

    // ── จ่าย / ใช้ <amount> <category> ──────────────
    const expMatch = text.match(/^(?:จ่าย|ใช้|exp(?:ense)?)\s+(\d+(?:\.\d+)?)\s+(.+)/i);
    if (expMatch) {
      saveExpense({ amount: expMatch[1], category: expMatch[2].trim() });
      reply = `✅ รายจ่าย: ${expMatch[2].trim()}\n฿${Number(expMatch[1]).toLocaleString('th-TH')}`;
    }

    // ── งาน / task <title> ────────────────────────────
    else if (/^(?:งาน|task)\s+/i.test(text)) {
      const title = text.replace(/^(?:งาน|task)\s+/i, '').trim();
      saveTask({ title });
      reply = `✅ เพิ่มงาน\n"${title}"`;
    }

    // ── โน้ต / note <content> ─────────────────────────
    else if (/^(?:โน้ต|note|memo)\s+/i.test(text)) {
      const content = text.replace(/^(?:โน้ต|note|memo)\s+/i, '').trim();
      saveNote({ title: content.slice(0, 40), content });
      reply = `✅ บันทึกโน้ต\n"${content.slice(0, 80)}"`;
    }

    // ── ดูรายจ่าย ────────────────────────────────────
    else if (/^(?:ดูรายจ่าย|รายจ่ายวันนี้|สรุปรายจ่าย)/i.test(text)) {
      const exps = getExpenses().filter(e => e.date === today());
      const total = exps.reduce((s, e) => s + Number(e.amount), 0);
      if (exps.length === 0) {
        reply = '📊 วันนี้ยังไม่มีรายจ่าย';
      } else {
        reply = `📊 รายจ่ายวันนี้ (${exps.length} รายการ)\nรวม ฿${total.toLocaleString('th-TH')}\n\n` +
          exps.slice(-5).map(e => `• ${e.category}  ฿${Number(e.amount).toLocaleString('th-TH')}`).join('\n');
      }
    }

    // ── ดูงาน ─────────────────────────────────────────
    else if (/^(?:ดูงาน|งานค้าง|งานวันนี้)/i.test(text)) {
      const tasks = getTasks().filter(t => t.status !== 'done');
      if (tasks.length === 0) {
        reply = '✅ ไม่มีงานค้าง 🎉';
      } else {
        reply = `📋 งานค้าง ${tasks.length} รายการ\n\n` +
          tasks.slice(0, 5).map(t => `• [${t.priority}] ${t.title}`).join('\n') +
          (tasks.length > 5 ? `\n...และอีก ${tasks.length - 5} รายการ` : '');
      }
    }

    // ── help ──────────────────────────────────────────
    else if (/^(?:help|ช่วย|คำสั่ง|menu)/i.test(text)) {
      reply = `📱 คำสั่ง LINE Dashboard\n\n` +
        `💰 รายจ่าย:\nจ่าย 150 อาหาร\nใช้ 500 ช้อปปิ้ง\n\n` +
        `✅ งาน:\nงาน ประชุม client วันพฤหัส\n\n` +
        `📝 โน้ต:\nโน้ต ข้อความที่ต้องการบันทึก\n\n` +
        `📊 ดูข้อมูล:\nดูรายจ่าย\nดูงาน`;
    }

    if (reply && replyToken) {
      replyToLine(token, replyToken, reply);
    }
  }
}

function replyToLine(token, replyToken, text) {
  UrlFetchApp.fetch('https://api.line.me/v2/bot/message/reply', {
    method: 'post',
    contentType: 'application/json',
    headers: { Authorization: `Bearer ${token}` },
    payload: JSON.stringify({ replyToken, messages: [{ type: 'text', text }] }),
    muteHttpExceptions: true,
  });
}

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

// ── Warmup (set as 5-min trigger to prevent cold starts) ─────

function warmup() {
  // Touch PropertiesService to keep script warm
  PropertiesService.getScriptProperties().getProperty('SPREADSHEET_ID');
  Logger.log('warmup ok ' + new Date().toISOString());
}

// ── HTTP: GET (also used as health check) ─────────────────────

// ── HTTP: POST ────────────────────────────────────────────────

function doPost(e) {
  // Always return 200 immediately — LINE webhook verify requires fast response
  const OK = ContentService.createTextOutput('{"ok":true}')
               .setMimeType(ContentService.MimeType.JSON);

  try {
    if (!e || !e.postData || !e.postData.contents) return OK;
    const body = JSON.parse(e.postData.contents);

    // ── LINE Webhook ──────────────────────────────────
    if (body.events !== undefined) {
      if (body.events.length === 0) return OK;   // verify ping — return instantly
      try { processLine(body.events); } catch(ex) { Logger.log('LINE err: '+ex); }
      return OK;
    }

    // ── Dashboard API Write ───────────────────────────
    const { action, record } = body;
    let result = { ok: false, error: 'Unknown action: ' + action };

    switch (action) {
      case 'saveExpense':      result = saveExpense(record);                         break;
      case 'deleteExpense':    deleteById('expense', record.id);   result = {ok:true}; break;
      case 'saveTask':         result = saveTask(record);                            break;
      case 'deleteTask':       deleteById('task', record.id);      result = {ok:true}; break;
      case 'saveNote':         result = saveNote(record);                            break;
      case 'deleteNote':       deleteById('note', record.id);      result = {ok:true}; break;
      case 'savePortfolio':    result = savePortfolio(record);                       break;
      case 'deletePortfolio':  deletePortfolioAll(record.id);      result = {ok:true}; break;
      case 'saveInvestment':   result = saveInvestment(record);                      break;
      case 'deleteInvestment': deleteById('investment', record.id); result = {ok:true}; break;
      case 'saveDividend':     result = saveDividend(record);                        break;
      case 'deleteDividend':   deleteById('dividend', record.id);  result = {ok:true}; break;
    }
    return jsonResp(result);

  } catch (err) {
    Logger.log('doPost err: ' + err);
    return OK;  // always 200 even on error
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
    if (ev.type !== 'message') continue;

    const replyTok = ev.replyToken;
    let reply = '';

    if (ev.message.type === 'text') {
      reply = buildReply(ev.message.text.trim()) || '';
    }
    else if (ev.message.type === 'image') {
      // 📸 Slip OCR flow
      reply = processSlipImage(ev.message.id, token);
    }

    if (reply && replyTok) replyToLine(token, replyTok, reply);
  }
}

// ── SLIP OCR ──────────────────────────────────────────────────

function processSlipImage(messageId, token) {
  try {
    // 1. Download image from LINE
    const blob = downloadLineImage(messageId, token);
    if (!blob) return '❌ ไม่สามารถดาวน์โหลดรูปได้';

    // 2. OCR via Google Drive (ฟรี ไม่ต้องใช้ Vision API)
    replyInProgress(token, messageId); // optional: ไม่ได้ใช้ แต่เตือนไว้
    const text = ocrWithDrive(blob);
    if (!text || text.trim().length < 3) {
      return '❌ อ่านข้อความจากรูปไม่ได้\nลองส่งรูปที่ชัดขึ้น หรือพิมพ์ "จ่าย [จำนวน] [หมวด]" แทน';
    }

    // 3. Parse amount
    const amount = parseSlipAmount(text);
    if (!amount) {
      return `📄 อ่านข้อความได้แต่ไม่พบจำนวนเงิน\n\n"${text.slice(0, 150)}"\n\nกรุณาพิมพ์:\nจ่าย [จำนวน] [หมวด]`;
    }

    // 4. Detect category & merchant
    const category = detectSlipCategory(text);
    const merchant = detectMerchant(text);
    const notes    = merchant ? `Slip: ${merchant}` : 'จาก Slip';

    // 5. Save expense
    saveExpense({ amount, category, notes });

    const fmt = Number(amount).toLocaleString('th-TH', { minimumFractionDigits: 2 });
    return `✅ บันทึกจาก Slip อัตโนมัติ\n` +
           `💰 ฿${fmt}\n` +
           `📂 ${category}` +
           (merchant ? `\n🏪 ${merchant}` : '') +
           `\n\nถ้าหมวดไม่ถูก พิมพ์:\nจ่าย ${Math.round(amount)} [หมวด]`;

  } catch (e) {
    Logger.log('Slip OCR error: ' + e);
    return '❌ เกิดข้อผิดพลาด: ' + e.message;
  }
}

function replyInProgress() {} // placeholder

function downloadLineImage(messageId, token) {
  const url = `https://api-data.line.me/v2/bot/message/${messageId}/content`;
  const res = UrlFetchApp.fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
    muteHttpExceptions: true,
  });
  if (res.getResponseCode() !== 200) return null;
  return res.getBlob().setName('slip.jpg');
}

function ocrWithDrive(blob) {
  // Upload to Drive with OCR → Google converts to Google Doc → extract text
  let fileId = null;
  try {
    const file = Drive.Files.insert(
      { title: 'slip_ocr_' + Date.now(), mimeType: 'application/vnd.google-apps.document' },
      blob,
      { convert: true, ocr: true, ocrLanguage: 'th' }
    );
    fileId = file.id;
    const doc  = DocumentApp.openById(fileId);
    const text = doc.getBody().getText();
    return text;
  } finally {
    if (fileId) {
      try { Drive.Files.remove(fileId); } catch(e) {}
    }
  }
}

function parseSlipAmount(text) {
  const patterns = [
    /จำนวนเงิน\s*:?\s*([\d,]+\.?\d*)\s*บาท/i,
    /ยอดเงิน\s*:?\s*([\d,]+\.?\d*)/i,
    /ยอดโอน\s*:?\s*([\d,]+\.?\d*)/i,
    /amount\s*:?\s*([\d,]+\.?\d*)/i,
    /total\s*:?\s*([\d,]+\.?\d*)/i,
    /รวม\s*:?\s*([\d,]+\.?\d*)\s*บาท/i,
    /฿\s*([\d,]+\.?\d*)/,
    /([\d,]+\.\d{2})\s*บาท/,
    /([\d,]+\.\d{2})\s*THB/i,
    /\bTHB\s*([\d,]+\.?\d*)/i,
  ];
  const candidates = [];
  for (const p of patterns) {
    const m = text.match(p);
    if (m) {
      const v = parseFloat(m[1].replace(/,/g, ''));
      if (v > 0 && v < 10000000) candidates.push(v);
    }
  }
  if (!candidates.length) return null;
  // Return the most prominent amount (largest candidate, likely the total)
  return Math.max(...candidates);
}

function detectSlipCategory(text) {
  const t = text.toLowerCase();
  if (/ร้านอาหาร|food|restaurant|mcdonald|kfc|pizza|burger|coffee|cafe|กาแฟ|ชา|ข้าว|หมู|ไก่|ปลา|ก๋วยเตี๋ยว|ส้มตำ|sushi|buffet|bakery/.test(t)) return 'อาหาร/เครื่องดื่ม';
  if (/grab|bolt|taxi|mrt|bts|รถไฟ|รถเมล์|parking|จอดรถ|น้ำมัน|ptt|bangchak|esso/.test(t)) return 'เดินทาง';
  if (/7-eleven|seven|lotus|big c|makro|tops|villa|supermarket|department|fashion|clothing|เสื้อ|กางเกง|รองเท้า/.test(t)) return 'ช้อปปิ้ง';
  if (/โรงพยาบาล|hospital|clinic|pharmacy|เภสัช|drugstore|ยา|นวด|spa/.test(t)) return 'สุขภาพ';
  if (/hotel|ที่พัก|resort|airbnb|agoda|booking/.test(t)) return 'ที่พัก';
  if (/netflix|spotify|youtube|steam|game|cinema|sf|major|imax|concert/.test(t)) return 'ความบันเทิง';
  if (/course|udemy|book|หนังสือ|เรียน|tutor|school|university/.test(t)) return 'การศึกษา';
  return 'อื่นๆ';
}

function detectMerchant(text) {
  // ลองหาชื่อร้านจาก pattern ทั่วไป
  const patterns = [
    /ร้าน[:\s]*([^\n]{2,30})/,
    /merchant[:\s]*([^\n]{2,30})/i,
    /จาก[:\s]*([^\n]{2,20})/,
    /to[:\s]*([^\n]{2,30})/i,
  ];
  for (const p of patterns) {
    const m = text.match(p);
    if (m) return m[1].trim().slice(0, 30);
  }
  return null;
}

function buildReply(text) {
  const t = text.trim();
  const lo = t.toLowerCase();

  // ── จ่าย / ใช้ [amount] [category] [note?] ───────────────────
  // รูปแบบ: จ่าย 150 อาหาร  หรือ  จ่าย 150 อาหาร ข้าวผัด
  const expMatch = t.match(/^(?:จ่าย|ใช้|expense)\s+(\d+(?:[.,]\d+)?)\s+([฀-๿a-zA-Z\/]+)(.*)?$/i);
  if (expMatch) {
    const amount   = parseFloat(expMatch[1].replace(',', ''));
    const category = expMatch[2].trim();
    const note     = (expMatch[3] || '').trim();
    saveExpense({ amount, category, notes: note });
    const fmt = amount.toLocaleString('th-TH', { minimumFractionDigits: 2 });
    return `✅ บันทึกรายจ่าย\n` +
           `💰 ${fmt} บาท\n` +
           `📂 ${category}` +
           (note ? `\n📝 ${note}` : '') +
           `\n\nพิมพ์ "ดูรายจ่าย" เพื่อดูสรุป`;
  }

  // ── งาน [title] [#high|#medium|#low?] ────────────────────────
  // รูปแบบ: งาน ประชุม client  หรือ  งาน งานด่วน #high
  else if (/^(?:งาน|task)\s+/i.test(t)) {
    const body     = t.replace(/^(?:งาน|task)\s+/i, '').trim();
    const priMatch = body.match(/#(high|medium|low|สูง|กลาง|ต่ำ)$/i);
    const priority = priMatch
      ? ({ high:'high',สูง:'high',medium:'medium',กลาง:'medium',low:'low',ต่ำ:'low' }[priMatch[1].toLowerCase()] || 'medium')
      : 'medium';
    const title    = body.replace(/#\S+$/, '').trim();
    saveTask({ title, priority });
    const priLabel = { high:'🔴 สูง', medium:'🟡 กลาง', low:'🟢 ต่ำ' }[priority];
    return `✅ เพิ่มงานใหม่\n📋 ${title}\n${priLabel} Priority\n\nพิมพ์ "ดูงาน" เพื่อดูงานค้าง`;
  }

  // ── งานเสร็จ [title fragment] ─────────────────────────────────
  else if (/^(?:งานเสร็จ|done)\s+/i.test(t)) {
    const frag  = t.replace(/^(?:งานเสร็จ|done)\s+/i, '').trim().toLowerCase();
    const tasks = getTasks().filter(tk => tk.status !== 'done');
    const found = tasks.find(tk => tk.title.toLowerCase().includes(frag));
    if (found) {
      saveTask({ ...found, status: 'done' });
      return `✅ มาร์คงานเสร็จแล้ว\n"${found.title}"`;
    }
    return `❌ ไม่พบงานที่มีคำว่า "${frag}"`;
  }

  // ── โน้ต / note / memo [content] ─────────────────────────────
  else if (/^(?:โน้ต|note|memo)\s+/i.test(t)) {
    const content  = t.replace(/^(?:โน้ต|note|memo)\s+/i, '').trim();
    const catMatch = content.match(/#(\S+)$/);
    const category = catMatch ? catMatch[1] : '';
    const body     = content.replace(/#\S+$/, '').trim();
    const title    = body.slice(0, 50);
    saveNote({ title, content: body, category });
    return `✅ บันทึกโน้ต\n"${title}"` + (category ? `\n📂 ${category}` : '');
  }

  // ── สรุป / ดูรายจ่าย [วันนี้|เดือนนี้|เดือน] ─────────────────
  else if (/^(?:ดูรายจ่าย|สรุปรายจ่าย|รายจ่าย|summary)/i.test(lo)) {
    const all       = getExpenses();
    const todayStr  = today();
    const monthStr  = todayStr.slice(0, 7);

    const isMonth   = /เดือน|month/i.test(t);
    const label     = isMonth ? `เดือน ${monthStr}` : `วันนี้ ${todayStr}`;
    const filtered  = isMonth
      ? all.filter(e => e.date.startsWith(monthStr))
      : all.filter(e => e.date === todayStr);

    const total     = filtered.reduce((s, e) => s + Number(e.amount || 0), 0);
    const fmt       = total.toLocaleString('th-TH', { minimumFractionDigits: 2 });

    if (!filtered.length) return `📊 ไม่มีรายจ่าย${isMonth ? 'เดือนนี้' : 'วันนี้'}`;

    // Group by category
    const bycat = {};
    filtered.forEach(e => { bycat[e.category] = (bycat[e.category] || 0) + Number(e.amount || 0); });
    const catLines = Object.entries(bycat)
      .sort((a, b) => b[1] - a[1])
      .map(([c, v]) => `  • ${c}: ฿${v.toLocaleString('th-TH')}`)
      .join('\n');

    return `📊 สรุปรายจ่าย ${label}\n` +
           `รวม ฿${fmt} (${filtered.length} รายการ)\n\n` +
           catLines;
  }

  // ── ดูงาน [all?] ─────────────────────────────────────────────
  else if (/^(?:ดูงาน|งานค้าง|งาน\?)/i.test(lo)) {
    const showAll   = /ทั้งหมด|all/i.test(t);
    const tasks     = getTasks();
    const pending   = tasks.filter(tk => tk.status !== 'done');
    const display   = showAll ? tasks : pending;

    if (!display.length) return `✅ ไม่มีงาน${showAll ? '' : 'ค้าง'} 🎉`;

    const priIcon   = { high:'🔴', medium:'🟡', low:'🟢' };
    const statIcon  = { todo:'📋', inprog:'⚡', done:'✅' };
    const lines     = display.slice(0, 8).map(tk =>
      `${priIcon[tk.priority] || '⚪'} ${tk.title} ${statIcon[tk.status] || ''}`
        + (tk.due ? ` (${tk.due})` : '')
    ).join('\n');

    return `${showAll ? '📋 งานทั้งหมด' : '📋 งานค้าง'} (${display.length} รายการ)\n\n${lines}` +
           (display.length > 8 ? `\n...และอีก ${display.length - 8} รายการ` : '');
  }

  // ── ดูโน้ต ────────────────────────────────────────────────────
  else if (/^(?:ดูโน้ต|โน้ตล่าสุด|note\?)/i.test(lo)) {
    const notes = getNotes().sort((a, b) => b.date.localeCompare(a.date)).slice(0, 5);
    if (!notes.length) return '📝 ยังไม่มีโน้ต';
    return `📝 โน้ตล่าสุด\n\n` +
      notes.map(n => `• ${n.title}${n.category ? ' [' + n.category + ']' : ''}\n  ${n.date}`).join('\n');
  }

  // ── help ──────────────────────────────────────────────────────
  else if (/^(?:help|ช่วย|คำสั่ง|menu|\?)/i.test(lo)) {
    return `📱 คำสั่ง LINE Bot\n` +
      `─────────────────\n` +
      `💰 บันทึกรายจ่าย\n` +
      `  จ่าย 150 อาหาร\n` +
      `  จ่าย 500 ช้อปปิ้ง กระเป๋า\n\n` +
      `✅ จัดการงาน\n` +
      `  งาน ชื่องาน\n` +
      `  งาน งานด่วน #high\n` +
      `  งานเสร็จ ชื่องาน\n\n` +
      `📝 บันทึกโน้ต\n` +
      `  โน้ต ข้อความ\n` +
      `  โน้ต ไอเดีย #Ideas\n\n` +
      `📊 ดูข้อมูล\n` +
      `  ดูรายจ่าย\n` +
      `  ดูรายจ่าย เดือนนี้\n` +
      `  ดูงาน\n` +
      `  ดูโน้ต`;
  }

  return null; // ไม่มีคำสั่งที่ตรงกัน — ไม่ตอบ
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

/**
 * Apps Script para sincronizar uma pasta do Google Drive com uma aba de controle.
 *
 * Fluxo:
 * 1) Varre a pasta do Drive
 * 2) Registra novos PDFs na aba 'processamento'
 * 3) O pipeline Python consome essa aba e marca os itens processados
 */

function registrarNovosArquivos() {
  const folderId = 'COLE_AQUI_O_ID_DA_PASTA_DO_DRIVE';
  const spreadsheetId = 'COLE_AQUI_O_ID_DA_PLANILHA';
  const sheetName = 'processamento';

  const folder = DriveApp.getFolderById(folderId);
  const spreadsheet = SpreadsheetApp.openById(spreadsheetId);
  let sheet = spreadsheet.getSheetByName(sheetName);

  if (!sheet) {
    sheet = spreadsheet.insertSheet(sheetName);
    sheet.appendRow(['id_origem', 'nome_arquivo', 'origem', 'processado_em']);
  }

  const values = sheet.getDataRange().getValues();
  const already = new Set(values.slice(1).map(row => String(row[0] || '').trim()));

  const files = folder.getFilesByType(MimeType.PDF);
  while (files.hasNext()) {
    const file = files.next();
    const fileId = file.getId();
    if (already.has(fileId)) {
      continue;
    }
    sheet.appendRow([fileId, file.getName(), 'google_drive', '']);
  }
}

function criarTrigger() {
  ScriptApp.newTrigger('registrarNovosArquivos')
    .timeBased()
    .everyMinutes(15)
    .create();
}

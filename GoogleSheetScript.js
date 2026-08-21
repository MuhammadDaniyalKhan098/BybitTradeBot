function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    
    sheet.appendRow([
      data.timestamp,
      data.symbol,
      data.action,
      data.status,
      data.details,
      data.original_msg
    ]);
    
    return ContentService.createTextOutput(JSON.stringify({'status': 'success'}))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({'status': 'error', 'message': error.toString()}))
      .setMimeType(ContentService.MimeType.JSON);
  }
}
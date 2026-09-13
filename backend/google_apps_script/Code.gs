/**
 * =============================================================================
 * CatalogIQ — Google Apps Script Production Email Relay Web App
 * =============================================================================
 * 
 * Backed by Gmail Account: dishasengar1june@gmail.com
 * 
 * Deployment Instructions:
 * 1. Open https://script.google.com and log in with dishasengar1june@gmail.com
 * 2. Click "New Project" and name it "CatalogIQ Email Relay"
 * 3. Replace all code in Code.gs with this entire file.
 * 4. Set your SHARED_SECRET below (or via Project Settings -> Script Properties).
 * 5. Click "Deploy" -> "New Deployment":
 *    - Select type: "Web App"
 *    - Description: "CatalogIQ Production Relay v1"
 *    - Execute as: "Me (dishasengar1june@gmail.com)"
 *    - Who has access: "Anyone" (Required for Render to POST without Google login)
 * 6. Click "Deploy", review & authorize Gmail permissions.
 * 7. Copy the Web App URL (ends with /exec) into Render Environment Variables:
 *    GOOGLE_APPS_SCRIPT_URL=https://script.google.com/macros/s/.../exec
 *    GOOGLE_APPS_SCRIPT_SECRET=your_secret_key_matching_below
 */

// Define the shared secret here (or set it in Script Properties with key 'SHARED_SECRET')
var SHARED_SECRET = "CHANGE_TO_A_STRONG_RANDOM_SECRET_KEY";

/**
 * Handle incoming HTTPS POST requests from CatalogIQ FastAPI Backend.
 * 
 * Expected JSON Body:
 * {
 *   "secret": "...",
 *   "to": "recipient@domain.com",
 *   "subject": "Email Subject",
 *   "html": "<html>...</html>",
 *   "text": "plain text fallback"
 * }
 */
function doPost(e) {
  try {
    // Validate request envelope
    if (!e || !e.postData || !e.postData.contents) {
      return createJsonResponse({
        success: false,
        error: "Bad Request: Missing request body"
      }, 400);
    }

    // Parse JSON payload
    var data;
    try {
      data = JSON.parse(e.postData.contents);
    } catch (parseErr) {
      return createJsonResponse({
        success: false,
        error: "Bad Request: Malformed JSON payload"
      }, 400);
    }

    // 1. Authenticate using Shared Secret
    var expectedSecret = PropertiesService.getScriptProperties().getProperty("SHARED_SECRET") || SHARED_SECRET;
    if (!data.secret || data.secret !== expectedSecret) {
      return createJsonResponse({
        success: false,
        error: "Unauthorized: Invalid or missing secret token"
      }, 401);
    }

    // 2. Validate Email Payload Fields
    var to = (data.to || "").trim();
    var subject = (data.subject || "").trim();
    var htmlBody = (data.html || "").trim();
    var textBody = (data.text || "").trim();

    if (!to) {
      return createJsonResponse({
        success: false,
        error: "Unprocessable Entity: Missing 'to' recipient address"
      }, 422);
    }

    if (!subject) {
      return createJsonResponse({
        success: false,
        error: "Unprocessable Entity: Missing 'subject' field"
      }, 422);
    }

    if (!htmlBody && !textBody) {
      return createJsonResponse({
        success: false,
        error: "Unprocessable Entity: Missing email content ('html' or 'text')"
      }, 422);
    }

    // 3. Dispatch Email via Gmail MailApp
    MailApp.sendEmail({
      to: to,
      subject: subject,
      body: textBody || "Please view this message in an HTML-compatible email client.",
      htmlBody: htmlBody || undefined,
      name: "CatalogIQ Access Desk"
    });

    // 4. Return Verified Success Response
    return createJsonResponse({
      success: true,
      message: "Email accepted by Gmail for " + to,
      recipient: to,
      timestamp: new Date().toISOString()
    }, 200);

  } catch (err) {
    // 5. Catch and return safe error without exposing internal secrets
    return createJsonResponse({
      success: false,
      error: "Gmail delivery exception: " + (err.message || err.toString())
    }, 500);
  }
}

/**
 * Handle HTTP GET requests for quick health check verification in browser.
 */
function doGet(e) {
  return createJsonResponse({
    status: "online",
    service: "CatalogIQ Google Apps Script Email Relay",
    account: Session.getActiveUser().getEmail() || "dishasengar1june@gmail.com",
    timestamp: new Date().toISOString()
  }, 200);
}

/**
 * Helper to build JSON ContentService response.
 */
function createJsonResponse(obj, statusCode) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

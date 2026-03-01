/**
 * Tether HTTP API -> Google Sheets Connector
 *
 * Bridges any non-MCP client (Gemini, Grok, ChatGPT, etc.) to Tether
 * by syncing data from the Tether HTTP API into Google Sheets tabs.
 *
 * Setup:
 *   1. Open Google Sheet -> Extensions -> Apps Script
 *   2. Paste this entire file
 *   3. Set TETHER_API_URL below (must be publicly reachable -- use ngrok if local)
 *   4. Save -> Run "onOpen" once to authorize
 *   5. Use the "Tether" menu in the sheet toolbar
 *
 * Auto-refresh:
 *   Tether menu -> "Enable Auto-Refresh (2 min)" creates a time-based trigger.
 *   Tether menu -> "Disable Auto-Refresh" removes it.
 *
 * Author: Jonas Cords (cordsjon) + Claude (Opus 4.6)
 */

// -- Configuration -----------------------------------------------------------
const TETHER_API_URL = "https://YOUR_NGROK_URL.ngrok-free.dev"; // No trailing slash
// ----------------------------------------------------------------------------

/**
 * Adds Tether menu to the spreadsheet toolbar.
 */
function onOpen() {
  SpreadsheetApp.getUi().createMenu("Tether")
    .addItem("Refresh All Tables", "refreshAllTables")
    .addItem("Refresh Messages", "refreshMessages")
    .addItem("Refresh Inbox (by agent)", "promptInbox")
    .addItem("Refresh Threads", "refreshThreads")
    .addSeparator()
    .addItem("Health Check", "showHealth")
    .addSeparator()
    .addItem("Enable Auto-Refresh (2 min)", "enableAutoRefresh")
    .addItem("Disable Auto-Refresh", "disableAutoRefresh")
    .addToUi();
}

// -- Core API Helpers --------------------------------------------------------

/**
 * Fetch JSON from the Tether HTTP API.
 */
function tetherFetch(endpoint) {
  var url = TETHER_API_URL + endpoint;
  var options = {
    method: "get",
    muteHttpExceptions: true,
    headers: {
      "Accept": "application/json",
      "ngrok-skip-browser-warning": "true" // Skip ngrok interstitial
    }
  };

  var response = UrlFetchApp.fetch(url, options);
  var code = response.getResponseCode();

  if (code !== 200) {
    throw new Error("Tether API returned " + code + ": " + response.getContentText().substring(0, 200));
  }

  return JSON.parse(response.getContentText());
}

/**
 * Write rows to a named sheet. Creates the sheet if it doesn't exist.
 * Clears existing content before writing.
 */
function writeToSheet(sheetName, headers, rows) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(sheetName);

  if (!sheet) {
    sheet = ss.insertSheet(sheetName);
  }

  sheet.clearContents();

  if (headers.length === 0 || rows.length === 0) {
    sheet.getRange(1, 1).setValue("No data -- last checked: " + new Date().toISOString());
    return sheet;
  }

  // Write header row
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.getRange(1, 1, 1, headers.length)
    .setFontWeight("bold")
    .setBackground("#E8EAF6");

  // Write data rows
  if (rows.length > 0) {
    sheet.getRange(2, 1, rows.length, headers.length).setValues(rows);
  }

  // Auto-resize columns
  for (var i = 1; i <= headers.length; i++) {
    sheet.autoResizeColumn(i);
  }

  // Add timestamp
  sheet.getRange(rows.length + 3, 1).setValue("Last updated: " + new Date().toISOString());
  sheet.getRange(rows.length + 3, 1).setFontColor("#999999").setFontSize(9);

  return sheet;
}

/**
 * Flatten a value for display in a cell. Objects/arrays become JSON strings.
 */
function flatten(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return value;
}

// -- Refresh Functions -------------------------------------------------------

/**
 * Refresh all tables -- creates one sheet per Tether table.
 */
function refreshAllTables() {
  var data = tetherFetch("/tables");
  var tableNames = Object.keys(data.tables);

  // Write overview sheet
  var overviewHeaders = ["Table", "Handle Count"];
  var overviewRows = tableNames.map(function(name) {
    return [name, data.tables[name]];
  });
  writeToSheet("_Tether Overview", overviewHeaders, overviewRows);

  // Write each table's data
  tableNames.forEach(function(tableName) {
    refreshTable(tableName);
  });

  SpreadsheetApp.getActiveSpreadsheet().toast(
    tableNames.length + " table(s) refreshed", "Tether", 3
  );
}

/**
 * Refresh a single table into its own sheet.
 */
function refreshTable(tableName) {
  var data = tetherFetch("/tables/" + encodeURIComponent(tableName));
  var entries = data.entries || [];

  if (entries.length === 0) {
    writeToSheet("tether:" + tableName, [], []);
    return;
  }

  // Collect all unique keys across all entries
  var keySet = {};
  entries.forEach(function(entry) {
    Object.keys(entry).forEach(function(key) {
      keySet[key] = true;
    });
  });

  // Put handle first, then sort the rest
  var headers = ["handle"];
  Object.keys(keySet).sort().forEach(function(key) {
    if (key !== "handle") headers.push(key);
  });

  var rows = entries.map(function(entry) {
    return headers.map(function(h) {
      return flatten(entry[h]);
    });
  });

  writeToSheet("tether:" + tableName, headers, rows);
}

/**
 * Refresh the messages table specifically.
 */
function refreshMessages() {
  var data = tetherFetch("/messages");
  var messages = data.messages || [];

  var headers = ["handle", "table", "from", "to", "subject", "text", "timestamp"];
  var rows = messages.map(function(msg) {
    return headers.map(function(h) {
      return flatten(msg[h]);
    });
  });

  writeToSheet("tether:all-messages", headers, rows);

  SpreadsheetApp.getActiveSpreadsheet().toast(
    messages.length + " message(s)", "Tether Messages", 3
  );
}

/**
 * Prompt user for agent name, then refresh that agent's inbox.
 */
function promptInbox() {
  var ui = SpreadsheetApp.getUi();
  var result = ui.prompt(
    "Tether Inbox",
    "Enter agent name (e.g., opus, kilo, gemini):",
    ui.ButtonSet.OK_CANCEL
  );

  if (result.getSelectedButton() !== ui.Button.OK) return;

  var agent = result.getResponseText().trim();
  if (!agent) return;

  refreshInbox(agent);
}

/**
 * Refresh inbox for a specific agent.
 */
function refreshInbox(agent) {
  var data = tetherFetch("/inbox/" + encodeURIComponent(agent));
  var messages = data.messages || [];

  var headers = ["handle", "from", "to", "subject", "text", "timestamp"];
  var rows = messages.map(function(msg) {
    return headers.map(function(h) {
      return flatten(msg[h]);
    });
  });

  writeToSheet("tether:inbox-" + agent, headers, rows);

  SpreadsheetApp.getActiveSpreadsheet().toast(
    messages.length + " message(s) for " + agent, "Tether Inbox", 3
  );
}

/**
 * Refresh all threads.
 */
function refreshThreads() {
  var data = tetherFetch("/threads");
  var threads = data.threads || [];

  var headers = ["handle", "name", "description"];
  var rows = threads.map(function(t) {
    return headers.map(function(h) {
      return flatten(t[h]);
    });
  });

  writeToSheet("tether:threads", headers, rows);

  // Also refresh each thread's messages
  threads.forEach(function(thread) {
    if (thread.name) {
      var threadData = tetherFetch("/threads/" + encodeURIComponent(thread.name));
      var msgs = threadData.messages || [];

      var msgHeaders = ["handle", "table", "from", "to", "subject", "text", "timestamp"];
      var msgRows = msgs.map(function(msg) {
        return msgHeaders.map(function(h) {
          return flatten(msg[h]);
        });
      });

      writeToSheet("tether:thread-" + thread.name, msgHeaders, msgRows);
    }
  });

  SpreadsheetApp.getActiveSpreadsheet().toast(
    threads.length + " thread(s) refreshed", "Tether Threads", 3
  );
}

/**
 * Show health check as a dialog.
 */
function showHealth() {
  try {
    var data = tetherFetch("/health");
    var tableInfo = Object.keys(data.tables || {}).map(function(t) {
      return "  " + t + ": " + data.tables[t] + " handles";
    }).join("\n");

    var msg = "Status: " + data.status +
      "\nDB: " + data.db +
      "\nSize: " + Math.round((data.db_size_bytes || 0) / 1024) + " KB" +
      "\nTotal handles: " + data.total_handles +
      "\n\nTables:\n" + (tableInfo || "  (none)") +
      "\n\nTimestamp: " + data.timestamp;

    SpreadsheetApp.getUi().alert("Tether Health Check", msg, SpreadsheetApp.getUi().ButtonSet.OK);
  } catch (e) {
    SpreadsheetApp.getUi().alert(
      "Tether Health Check",
      "FAILED: " + e.message + "\n\nIs the API running? Check: " + TETHER_API_URL + "/health",
      SpreadsheetApp.getUi().ButtonSet.OK
    );
  }
}

// -- Auto-Refresh Trigger ----------------------------------------------------

/**
 * Enable auto-refresh every ~2 minutes.
 */
function enableAutoRefresh() {
  // Remove existing triggers first
  disableAutoRefresh();

  ScriptApp.newTrigger("autoRefresh")
    .timeBased()
    .everyMinutes(1) // Minimum Apps Script interval; effectively ~1-2 min
    .create();

  SpreadsheetApp.getActiveSpreadsheet().toast(
    "Auto-refresh enabled (every ~2 min)", "Tether", 5
  );
}

/**
 * Disable auto-refresh.
 */
function disableAutoRefresh() {
  var triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(function(trigger) {
    if (trigger.getHandlerFunction() === "autoRefresh") {
      ScriptApp.deleteTrigger(trigger);
    }
  });

  SpreadsheetApp.getActiveSpreadsheet().toast(
    "Auto-refresh disabled", "Tether", 3
  );
}

/**
 * Auto-refresh handler -- called by time trigger.
 * Only refreshes existing tether: sheets (doesn't create new ones).
 */
function autoRefresh() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheets = ss.getSheets();

  var refreshed = 0;

  sheets.forEach(function(sheet) {
    var name = sheet.getName();

    if (name === "_Tether Overview") {
      refreshAllTables();
      refreshed++;
    } else if (name === "tether:all-messages") {
      refreshMessages();
      refreshed++;
    } else if (name.indexOf("tether:inbox-") === 0) {
      var agent = name.replace("tether:inbox-", "");
      refreshInbox(agent);
      refreshed++;
    }
    // Individual table sheets (tether:*) are covered by refreshAllTables
  });

  // If no tether sheets exist yet, do a full refresh
  if (refreshed === 0) {
    refreshAllTables();
  }
}

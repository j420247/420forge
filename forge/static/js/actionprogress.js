var refreshLogsTimer;
var refreshStackInfoTimer;

function onReady() {
    $("#action-button").hide();
    $("#stackSelector").hide();

    // fix action string
    if (action.indexOf("/") !== -1)
        action = action.substr(action.indexOf("/") + 1);

    var params = new URL(window.location).searchParams;
    var stack_name = params.get("stack");
    if (params.has("region"))
        region = params.get("region");
    selectStack(stack_name);
    clearTimeout(refreshLogsTimer);
    clearTimeout(refreshStackInfoTimer);
    refreshLogs(stack_name, true, 3000, action);
    refreshStackInfo(stack_name, region, true);
}

// Refresh the status while the action is still underway
function refreshLogs(stack_name, cont, refresh_interval, this_action) {
    if (cont) {
        refreshLogsTimer = setTimeout(function () {
            getLogs(stack_name);

            // Stop once action is complete
            var logText = $("#log").contents().text().toLowerCase();
            if (action === 'diagnostics' && countOccurences(logText, "dumps complete") >= 1 ||
            countOccurences(logText
                    .replace(/ restart/g, 'restart')
                    .replace(/run sql/g, 'runsql')
                    .replace(/changeset execution/g, 'update'),
                    (this_action.toLowerCase() + " complete")) >= 1) {
                notify(this_action + " is complete");
                refreshLogs(stack_name, false, 0, this_action);
            }
            else
                refreshLogs(stack_name, true, 5000, this_action);
        }, refresh_interval)
    } else {
        refreshStackInfo(stack_name, region, false);
        clearTimeout(refreshLogsTimer);
    }
}

function refreshStackInfo(stack_name, region, cont) {
    // Refresh every 10s
    //TODO check more frequently until stack_state is IN_PROGRESS
    if (cont) {
        refreshStackInfoTimer = setTimeout(function () {
            updateStackInfo(stack_name, region);
            refreshStackInfo(stack_name, region, true);
        }, 10000)
    } else {
        updateStackInfo(stack_name, region);
        clearTimeout(refreshStackInfoTimer);
    }
}

function getLogs(stack_name) {
    if (stack_name === 'actionreadytostart') return;

    $("#log").css("background", "rgba(0,20,70,.08)");
    send_http_get_request(baseUrl + "/getLogs/" + stack_name, displayLogs)
}

function displayLogs(responseText) {
    var userHasScrolled = false;
    if ($("#log").contents().find('body').scrollTop() + $("#log").height() < $("#log").contents().height())
        userHasScrolled = true;

    $("#log").css("background", "rgba(0,0,0,0)");

    // If getting the logs has blipped, don't overwrite legitimate logging
    if ((countOccurences($("#log").contents().text(), "No current status for") !== 1 &&
        countOccurences($("#log").contents().text(), "Waiting for logs") !== 1)
        &&
        (countOccurences(responseText, "No current status for") === 1 ||
            countOccurences(responseText, "Waiting for logs") === 1))
        return;

    $("#log").contents().find('body').html(responseText
        .substr(1, responseText.length - 3)
        .split('",').join('<br />')
        .split('\\n').join('<br />')
        .split('"').join('')
        .trim());

    if (! userHasScrolled)
        $("#log").contents().find('body').scrollTop(9999999999);
}
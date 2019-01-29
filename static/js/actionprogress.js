var refreshLogsTimer;
var refreshStackInfoTimer;

function onReady() {
    var stacks = document.getElementsByClassName("selectStackOption");
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
    getLogs(stack_name);
    updateStats(stack_name, region);
    refreshLogs(stack_name, true, 2000, action);
    refreshStackInfo(stack_name, region, true);
}

// Refresh the status while the action is still underway
function refreshLogs(stack_name, cont, refresh_interval, this_action) {
    if (cont) {
        refreshLogsTimer = setTimeout(function () {
            getLogs(stack_name);

            // Set refresh interval to more frequent if there is no logging yet
            if (countOccurences($("#log").contents().text(), "No current status for") >= 1 ||
                countOccurences($("#log").contents().text(), "Waiting for logs") >= 1 )
                refresh_interval = 1000;

            // Stop once action is complete
            refresh_interval = 5000;
            if (action === 'diagnostics') {
                if (countOccurences($("#log").contents().text().toLowerCase(), "beginning thread dumps") >= 1 &&
                    countOccurences($("#log").contents().text().toLowerCase(), "thread dumps complete") !== 1)
                    refreshLogs(stack_name, true, refresh_interval, this_action);
                else if (countOccurences($("#log").contents().text().toLowerCase(), "beginning heap dumps") >= 1 &&
                    countOccurences($("#log").contents().text().toLowerCase(), "heap dumps complete") !== 1)
                    refreshLogs(stack_name, true, refresh_interval, this_action);
                else {
                    notify(this_action + " is complete");
                    refreshLogs(stack_name, false, refresh_interval, this_action);
                }
            }
            else if (countOccurences($("#log").contents().text().toLowerCase()
                    .replace(/ dumps/g, 'dumps')
                    .replace(/ restart/g, 'restart')
                    .replace(/run sql/g, 'runsql'),
                    (this_action.toLowerCase() + " complete")) >= 1) {
                notify(this_action + " is complete");
                refreshLogs(stack_name, false, refresh_interval, this_action);
            }
            else
                refreshLogs(stack_name, true, refresh_interval, this_action);
        }, refresh_interval)
    } else {
        refreshStackInfo(stack_name, region, false);
        clearTimeout(refreshLogsTimer); // TODO create function to check action complete and clear all timers
    }
}

function refreshStackInfo(stack_name, region, cont) {
    // Refresh every 10s
    //TODO check more frequently until stack_state is IN_PROGRESS
    if (cont) {
        refreshStackInfoTimer = setTimeout(function () {
            updateStats(stack_name, region);
            refreshStackInfo(stack_name, region, true);
        }, 10000)
    } else {
        updateStats(stack_name, region);
        clearTimeout(refreshStackInfoTimer);
    }
}

function getLogs(stack_name) {
    if (stack_name === 'actionreadytostart') return;

    $("#log").css("background", "rgba(0,20,70,.08)");

    send_http_get_request(baseUrl + "/getLogs/" + stack_name, displayLogs)
}

function displayLogs(responseText) {
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

    $("#log").contents().find('body').scrollTop(9999999999);
}
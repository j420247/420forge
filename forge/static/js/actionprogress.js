var refreshLogsTimer;
var refreshStackInfoInterval;

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
    refreshLogs(stack_name, 2000, action);
    refreshStackInfo(stack_name, region, action);
}

function action_complete(this_action) {
    var logText = $("#log").contents().text().toLowerCase();
    return countOccurences(logText
            .replace(/ restart/g, 'restart')
            .replace(/run sql/g, 'runsql')
            .replace(/changeset execution/g, 'update')
            .replace(/(thread|heap) dumps/g, 'diagnostics'),
        (this_action.toLowerCase() + " complete")) >= 1;
}

// Refresh the logs while the action is still underway
function refreshLogs(stack_name, refresh_interval, this_action) {
    refreshLogsTimer = setTimeout(function () {
        getLogs(stack_name);
        // Stop once action is complete
        if (action_complete(this_action)) {
            notify(this_action + " is complete");
            clearTimeout(refreshLogsTimer);
        } else {
            // Otherwise keep refreshing
            refreshLogs(stack_name, 5000, this_action);
        }
    }, refresh_interval)
}

function refreshStackInfo(stack_name, region, this_action) {
    // Refresh stack info every 10s
    refreshStackInfoInterval = setInterval(function () {
        updateStackInfo(stack_name, region);
    }, 10000);
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
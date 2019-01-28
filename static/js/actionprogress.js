var refreshLogsTimer;
var refreshStackInfoTimer;

function onReady() {
    var stacks = document.getElementsByClassName("selectStackOption");
    $("#action-button").hide();

    // fix action string
    if (action.indexOf("/") !== -1)
        action = action.substr(action.indexOf("/") + 1);

    // Set up stack selector if we are in viewlog
    if (action === 'viewlog') {
        for (var i = 0; i < stacks.length; i++) {
            stacks[i].addEventListener("click", function (data) {
                var stack_name = data.target.text;
                selectStack(stack_name);
                clearTimeout(refreshLogsTimer);
                clearTimeout(refreshStackInfoTimer);
                getStatus(stack_name);
                updateStats(stack_name);
                refreshLogs(stack_name, true, 2000, action);
                refreshStackInfo(stack_name, region, true);
            }, false);
        }
    // or if we got here from an action, refresh info now,
    // unless it's create in which case wait 2s for the creation to begin
    } else {
        var params = new URL(window.location).searchParams;
        var stack_name = params.get("stack");
        var region = params.get("region");
        $("#stackSelector").hide();
        selectStack(stack_name);
        if (action !== 'create')
            getStatus(stack_name);
        refreshLogs(stack_name, true, 2000, action);
        refreshStackInfo(stack_name, region, true);
    }
}

// Refresh the status while the action is still underway
function refreshLogs(stack_name, cont, refresh_interval, this_action) {
    if (cont) {
        refreshLogsTimer = setTimeout(function () {
            getStatus(stack_name);

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
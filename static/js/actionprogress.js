var refreshLogsTimer;
var refreshStackInfoTimer;
var actionProgressBegun;
var actionProgressComplete;

function onReady() {
    var stacks = document.getElementsByClassName("selectStackOption");
    $("#action-button").hide();

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
                refreshLogs(stack_name, true, 1000, action);
                refreshStackInfo(stack_name);
            }, false);
        }
    // or if we got here from an action, refresh info now,
    // unless it's create in which case wait 2s for the creation to begin
    } else {
        var stack_name = new URL(window.location).searchParams.values().next().value;
        $("#stackSelector").hide();
        selectStack(stack_name);
        if (action !== 'create')
            getStatus(stack_name);
        refreshLogs(stack_name, true, 2000, action);
        refreshStackInfo(stack_name);
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
                    countOccurences($("#log").contents().text().toLowerCase(), "thread dumps complete") != 1)
                    refreshLogs(stack_name, true, refresh_interval, this_action);
                else if (countOccurences($("#log").contents().text().toLowerCase(), "beginning heap dumps") >= 1 &&
                    countOccurences($("#log").contents().text().toLowerCase(), "heap dumps complete") != 1)
                    refreshLogs(stack_name, true, refresh_interval, this_action);
                else
                    refreshLogs(stack_name, false, refresh_interval, this_action);
            }
            else if (countOccurences($("#log").contents().text().toLowerCase(), this_action.replace(' ', '').toLowerCase() + " complete") >= 1)
                refreshLogs(stack_name, false, refresh_interval, this_action);
            else
                refreshLogs(stack_name, true, refresh_interval, this_action);
        }, refresh_interval)
    }
}

function refreshStackInfo(stack_name, this_action) {
    // Only check stack status in EC2 for stack changing actions
    // Refresh every 1s until action is in progress, then every 20s
    var refreshInterval = 1000;
    if (document.getElementById("stackState") &&
        document.getElementById("stackState").hasChildNodes()) {
        if (document.getElementById("stackState").childNodes[1].innerText.indexOf("IN_PROGRESS") === -1) {
            if (actionProgressBegun) {
                actionProgressComplete = true;
            }
        } else if (!actionProgressBegun) {
            actionProgressBegun = true;
            refreshInterval = 20000;
        }
    }

    if (this_action !== 'diagnostics' &&
        this_action !== 'fullrestart' &&
        this_action !== 'rollingrestart') {
        refreshStackInfoTimer = setTimeout(function () {
            updateStats(stack_name);
            refreshStackInfo(stack_name, this_action);
        }, refreshInterval)
    }
}
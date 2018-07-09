$(document).unbind('ready');

var refreshTimer;

$(document).ready(function() {
    var stacks = document.getElementsByClassName("selectStackOption");
    $("#action-button").hide();

    // Set up stack selector if we are in viewlog
    if (action === 'viewlog') {
        for (var i = 0; i < stacks.length; i++) {
            stacks[i].addEventListener("click", function (data) {
                var stack_name = data.target.text;
                selectStack(stack_name);
                clearTimeout(refreshTimer);
                getStatus(stack_name);
                updateStats(stack_name);
                refreshStatus(stack_name, true, 1000, action);
            }, false);
        }
    // or if we got here from an action, refresh info now,
    // unless it's create in which case wait 1s for the creation to begin
    } else {
        $("#stackSelector").hide();
        selectStack(stackName);
        if (action !== 'create') getStatus(stackName);
        refreshStatus(stackName, true, 2000, action);
    }
});

// Refresh the status while the action is still underway
function refreshStatus(stack_name, cont, refresh_interval, this_action) {
    if (cont) {
        refreshTimer = setTimeout(function () {
            getStatus(stack_name);

            // Only check stack status in EC2 for stack changing actions
            if (this_action !== 'diagnostics' &&
                this_action !== 'fullrestart' &&
                this_action !== 'rollingrestart') {
                updateStats(stack_name);
            }

            // Set refresh interval to more frequent if there is no logging yet
            if (countOccurences($("#log").contents().text(), "No current status for") >= 1 ||
                countOccurences($("#log").contents().text(), "Waiting for logs") >= 1 )
                refresh_interval = 1000;

            // Stop once action is complete
            refresh_interval = 5000;
            if (action === 'diagnostics') {
                if (countOccurences($("#log").contents().text().toLowerCase(), "beginning thread dumps") >= 1 &&
                    countOccurences($("#log").contents().text().toLowerCase(), "thread dumps complete") != 1)
                    refreshStatus(stack_name, true, refresh_interval, this_action);
                else if (countOccurences($("#log").contents().text().toLowerCase(), "beginning heap dumps") >= 1 &&
                    countOccurences($("#log").contents().text().toLowerCase(), "heap dumps complete") != 1)
                    refreshStatus(stack_name, true, refresh_interval, this_action);
                else
                    refreshStatus(stack_name, false, refresh_interval, this_action);
            }
            else if (countOccurences($("#log").contents().text().toLowerCase(), this_action.replace(' ', '').toLowerCase() + " complete") >= 1)
                refreshStatus(stack_name, false, refresh_interval, this_action);
            else
                refreshStatus(stack_name, true, refresh_interval, this_action);
        }, refresh_interval)
    }
}
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
                refreshStatus(stack_name, true, 1000);
            }, false);
        }
    // or if we got here from an action, refresh info now,
    // unless it's create in which case wait 1s for the creation to begin
    } else {
        $("#stackSelector").hide();
        selectStack(stackName);
        if (action !== 'create') getStatus(stackName);
        refreshStatus(stackName, true, 2000);
    }
});

// Refresh the status while the action is still underway
function refreshStatus(stack_name, cont, refresh_interval) {
    if (cont) {
        refreshTimer = setTimeout(function () {
            getStatus(stack_name);

            // Only check stack status in EC2 for stack changing actions
            if (action !== 'diagnostics' &&
                action !== 'fullrestart' &&
                action !== 'rollingrestart') {
                updateStats(stack_name);
                refresh_interval = 60000;
            }
            else
                refresh_interval = 10000;

            // Set refresh interval to more frequent if there is no logging yet
            if (countOccurences($("#log").contents().text(), "No current status for") >= 1 ||
                countOccurences($("#log").contents().text(), "Waiting for logs") >= 1 )
                refresh_interval = 1000;

            // Stop once action is complete
            if (countOccurences($("#log").contents().text().toLowerCase(), action.replace(' ', '').toLowerCase() + " complete") >= 1)
                refreshStatus(stack_name, false, refresh_interval);
            else
                refreshStatus(stack_name, true, refresh_interval);
        }, refresh_interval)
    }
}
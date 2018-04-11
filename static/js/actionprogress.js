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
    // or if we got here from an action, refresh info now
    } else {
        $("#stackSelector").hide();
        selectStack(stackName);
        getStatus(stackName);
        refreshStatus(stackName, true, 1000);
    }
});

// Refresh the status while the action is still underway
function refreshStatus(stack_name, cont, refresh_interval) {
    if (cont) {
        refreshTimer = setTimeout(function () {
            getStatus(stack_name);

            if (action !== 'diagnostics')
                updateStats(stack_name);

            // Set refresh interval sensibly
            if (countOccurences($("#log").contents().text(), "No current status for") === 1)
                refresh_interval = 1000;
            else
                refresh_interval = 30000;

            // If the stack was deleted as part of clone, ignore first 'Final state' and keep refreshing
            var expectedFinalState = 1;
            if (countOccurences($("#log").contents().text(), "Initiating clone") === 1 && countOccurences($("#log").contents().text(), "DELETE_IN_PROGRESS") >= 1)
                expectedFinalState = 2;
            if (countOccurences($("#log").contents().text(), "Final state") >= expectedFinalState) {
                refreshStatus(stack_name, false, refresh_interval);
            } else {
                refreshStatus(stack_name, true, refresh_interval);
            }
        }, refresh_interval)
    }
}
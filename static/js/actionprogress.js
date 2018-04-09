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
                refreshStatus(stack_name, true);
            }, false);
        }
    // or if we got here from an action, refresh info now
    } else {
        $("#stackSelector").hide();
        selectStack(stackName);
        getStatus(stackName);
        refreshStatus(stackName, true);
    }
});

// Refresh the status every 30s while the action is still underway
function refreshStatus(stack_name, cont) {
    if (cont) {
        refreshTimer = setTimeout(function () {
            getStatus(stack_name);
            updateStats(stack_name);
            // If the stack was deleted as part of clone, ignore first 'Final state' and keep refreshing
            var expectedFinalState = 1;
            if (countOccurences($("#log").contents().text(), "Initiating clone") === 1 && countOccurences($("#log").contents().text(), "DELETE_IN_PROGRESS") >= 1)
                expectedFinalState = 2;
            if (countOccurences($("#log").contents().text(), "Final state") >= expectedFinalState) {
                refreshStatus(stack_name, false);
            } else {
                refreshStatus(stack_name, true);
            }
        }, 30000)
    }
}
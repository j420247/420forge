function onReady() {
    addStackDropdown();
    $("#action-button").on("click", confirmSleep);
}

function confirmSleep() {
    var stackName = scrapePageForStackName();
    $("#stack-to-delete").text(stackName);
    send_http_get_request([baseUrl, 'hasTerminationProtection', region, stackName].join('/'), displaySleepModal);
}

function displaySleepModal(responseText) {
    var terminationProtection = JSON.parse(responseText);
    var stackName = scrapePageForStackName();
    if (terminationProtection) {
        var title = 'Cannot sleep ' + stackName;
        var text = 'At least one EC2 node has termination protection enabled. Please disable termination protection prior to sleeping.';
        $("#modal-ok-btn").html("Acknowledge");
        replaceModalContents(title, text);

        // Close modal on ACK
        $("#modal-ok-btn").on("click", function() {
            AJS.dialog2("#modal-dialog").hide();
        });
    } else {
        // Add action to OK button
        $("#modal-ok-btn").on("click", function() {
            send_http_get_request([baseUrl, 'dosleep', region, stackName].join('/'));
            redirectToLog(stackName, '');
        });
    }

    AJS.dialog2("#modal-dialog").show();
}
function onReady() {
    addStackDropdown();
    $("#action-button").on("click", confirmWake);
}

function confirmWake() {
    var stackName = scrapePageForStackName();
    $("#stack-to-delete").text(stackName);
    send_http_get_request([baseUrl, 'hasTerminationProtection', region, stackName].join('/'), displayWakeModal);
}

function displayWakeModal(responseText) {
    // Add action to OK button
    $("#modal-ok-btn").on("click", function() {
        send_http_get_request([baseUrl, 'dowake', region, stackName].join('/'));
        redirectToLog(stackName, '');
    });

    AJS.dialog2("#modal-dialog").show();
}
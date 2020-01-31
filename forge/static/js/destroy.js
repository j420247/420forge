function onReady() {
    addStackDropdown();
    $("#action-button").on("click", confirmDeletion);
}

function confirmDeletion() {
    var stackName = scrapePageForStackName();
    $("#stack-to-delete").text(stackName);
    send_http_get_request([baseUrl, 'hasTerminationProtection', region, stackName].join('/'), displayDestroyModal);
}

function displayDestroyModal(responseText) {
    var terminationProtection = JSON.parse(responseText);
    var stackName = scrapePageForStackName();
    if (terminationProtection) {
        var title = 'Cannot delete ' + stackName;
        var text = 'At least one EC2 node has termination protection enabled. Please disable termination protection prior to deletion.';
        replaceModalContents(title, text);
        // Close modal on OK
        $("#modal-ok-btn").on("click", function() {
            AJS.dialog2("#modal-dialog").hide();
        });
    } else {
        // Add action to OK button
        $("#modal-ok-btn").on("click", function() {
            send_http_get_request([baseUrl, 'dodestroy', region, stackName, $("#deleteChangelogs").is(":checked")].join('/'));
            redirectToLog(stackName, '');
        });
    }

    AJS.dialog2("#modal-dialog").show();
}
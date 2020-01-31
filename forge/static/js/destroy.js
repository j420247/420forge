function onReady() {
    addStackDropdown();
    $("#action-button").on("click", confirmDeletion);
}

function confirmDeletion() {
    var stackName = scrapePageForStackName();
    $("#stack-to-delete").text(stackName);
    AJS.dialog2("#modal-dialog").show();
    $("#modal-ok-btn").on("click", function() {
            send_http_get_request([baseUrl, 'dodestroy', region, stackName, $("#deleteChangelogs").is(":checked")].join('/'));
        redirectToLog(stackName, '');
    });
}
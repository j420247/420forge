function onReady() {
    addStackDropdown();
    $("#action-button").on("click", performWake);
}

function performWake() {
    var stackName = scrapePageForStackName();
    $("#stack-to-wake").text(stackName);
    send_http_get_request([baseUrl, 'dowake', region, stackName].join('/'));
    redirectToLog(stackName);
}

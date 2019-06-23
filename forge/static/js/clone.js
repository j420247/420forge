function onReady() {
    readyTheTemplate();
    getTemplates("Clone");
    var regions = document.getElementsByClassName("selectRegionOption");
    for (var i = 0; i < regions.length; i++) {
        regions[i].addEventListener("click", function (data) {
            var clone_region = data.target.text;
            $("#regionSelector").text(clone_region);
            $("#ebsSnapshotSelector").text("Select EBS snapshot");
            $("#rdsSnapshotSelector").text("Select RDS snapshot");
            getSnapshots(clone_region, document.getElementById("stackSelector").innerText);
            getVPCs(clone_region);
            getKmsKeyArn(clone_region)
        }, false);
    }
}

function getCloneDefaults(){
    var stack_name = $("#StackNameVal").val();
    if (!stack_name) {
        AJS.flag({
            type: 'error',
            body: 'Please enter a stack name',
            close: 'auto'
        });
        return;
    }
    send_http_get_request(baseUrl + "/getCloneDefaults/" + stack_name, applyCloneDefaults);
}

function applyCloneDefaults(responseText) {
    var params = JSON.parse(responseText);
    if (params.length === 0) {
        AJS.flag({
            type: 'error',
            body: 'No defaults exist for ' + $("#StackNameVal").val(),
            close: 'auto'
        });
        return;
    }

    for (var param in params) {
        var element = $("#" + param + "Val");
        if (element.is("input"))
            element.val(params[param]);
        else if (element.is("a"))
            element.text(params[param]);
    }
    AJS.flag({
        type: 'success',
        body: 'Defaults for ' + $("#StackNameVal").val() + ' have been applied',
        close: 'auto'
    });
}
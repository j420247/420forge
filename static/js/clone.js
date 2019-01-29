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
            getEbsSnapshots(clone_region, document.getElementById("stackSelector").innerText);
            getRdsSnapshots(clone_region, document.getElementById("stackSelector").innerText);
            getVPCs(clone_region, document.getElementById("VPCDiv"));
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
    if (params.length == 0) {
        AJS.flag({
            type: 'error',
            body: 'No defaults exist for ' + stack_name,
            close: 'auto'
        });
        return;
    }

    for (var param in params) {
        var element = $("#" + params[param][0] + "Val");
        if (element.is("input"))
            element.val(params[param][1]);
        else if (element.is("a"))
            element.text(params[param][1]);
    }
    AJS.flag({
        type: 'success',
        body: 'Defaults for ' + stack_name + ' have been applied',
        close: 'auto'
    });
}
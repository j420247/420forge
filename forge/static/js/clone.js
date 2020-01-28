function onReady() {
    readyTheTemplate();

    // Add event listener for stack dropdown
    var stacks = document.getElementsByClassName("selectStackOption");
    for (var i = 0; i < stacks.length; i++) {
        stacks[i].addEventListener("click", function (data) {
            templateHandler(data.target.text);
        });
    }

    getTemplates("Clone");

    $('#regionSelector').change(function() {
        var clone_region = this.value;
        getSnapshots(clone_region, document.getElementById("stackSelector").innerText);
        getVPCs(clone_region);
        getKmsKeys(clone_region);
    });
}

function getCloneDefaults(){
    var stack_name = $("#StackNameVal").val();
    if (!stack_name) {
        displayAUIFlag('Please enter a stack name', 'error');
        return;
    }
    send_http_get_request(baseUrl + "/getCloneDefaults/" + stack_name, applyCloneDefaults);
}

function applyCloneDefaults(responseText) {
    var params = JSON.parse(responseText);
    if (params.length === 0) {
        displayAUIFlag('No defaults exist for ' + $("#StackNameVal").val(), 'error');
        return;
    }

    for (var param in params) {
        var element = $("#" + param + "Val");
        if (element.is("input"))
            element.val(params[param]);
        else if (element.is("a"))
            element.text(params[param]);
        else if (element.is("aui-select"))
            element[0].value = params[param];
    }
    displayAUIFlag('Defaults for ' + $("#StackNameVal").val() + ' have been applied', 'success');
}

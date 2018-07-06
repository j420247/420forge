function onReady() {
    var regions = document.getElementsByClassName("selectRegionOption");
    for (var i = 0; i < regions.length; i++) {
        regions[i].addEventListener("click", function (data) {
            var region = data.target.text;
            $("#regionSelector").text(region);
            $("#ebsSnapshotSelector").text("Select EBS snapshot");
            $("#rdsSnapshotSelector").text("Select RDS snapshot");
            getEbsSnapshots(region, document.getElementById("stackSelector").innerText);
            getRdsSnapshots(region, document.getElementById("stackSelector").innerText);
            var regionEnv = env;
            if (action === 'clone') {
                if (region === "us-east-1")
                    regionEnv = "stg";
                else
                    regionEnv = "prod";
            }
            getVPCs(regionEnv, document.getElementById("VPCDiv"));
        }, false);
    }
}
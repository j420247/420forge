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
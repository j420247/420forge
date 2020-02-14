from flask import Blueprint
from flask_restful import Api
from forge.acforge import *


api_blueprint = Blueprint('api', __name__)
api = Api(api_blueprint)

# Actions
api.add_resource(DoUpgrade, '/doupgrade/<region>/<stack_name>/<new_version>/<zdu>')
api.add_resource(DoClone, '/doclone')
api.add_resource(DoFullRestart, '/dofullrestart/<region>/<stack_name>/<threads>/<heaps>')
api.add_resource(DoRollingRestart, '/dorollingrestart/<region>/<stack_name>/<threads>/<heaps>')
api.add_resource(DoRollingRebuild, '/dorollingrebuild/<region>/<stack_name>')
api.add_resource(DoCreate, '/docreate')
api.add_resource(DoDestroy, '/dodestroy/<region>/<stack_name>/<delete_changelogs>/<delete_threaddumps>')
api.add_resource(DoUpdate, '/doupdate/<stack_name>')
api.add_resource(DoExecuteChangeset, '/doexecutechangeset/<stack_name>/<change_set_name>')
api.add_resource(DoThreadDumps, '/dothreaddumps/<region>/<stack_name>')
api.add_resource(DoGetThreadDumpLinks, '/dogetthreaddumplinks/<region>/<stack_name>')
api.add_resource(DoHeapDumps, '/doheapdumps/<region>/<stack_name>')
api.add_resource(DoRunSql, '/dorunsql/<region>/<stack_name>')
api.add_resource(DoWake, '/dowake/<region>/<stack_name>')
api.add_resource(DoTag, '/dotag/<region>/<stack_name>')

# Stack info
api.add_resource(GetLogs, '/getLogs/<stack_name>')
api.add_resource(GetSysLogs, '/getSysLogs/')
api.add_resource(ServiceStatus, '/serviceStatus/<region>/<stack_name>')
api.add_resource(StackState, '/stackState/<region>/<stack_name>')
api.add_resource(TemplateParamsForStack, '/stackParams/<region>/<stack_name>/<template_name>')
api.add_resource(TemplateParams, '/templateParams/<repo_name>/<template_name>')
api.add_resource(GetSql, '/getsql/<region>/<stack_name>')
api.add_resource(GetStackActionInProgress, '/getActionInProgress/<region>/<stack_name>')
api.add_resource(ClearStackActionInProgress, '/clearActionInProgress/<region>/<stack_name>')
api.add_resource(GetVersion, '/getVersion/<region>/<stack_name>')
api.add_resource(GetNodes, '/getNodes/<region>/<stack_name>')
api.add_resource(GetTags, '/getTags/<region>/<stack_name>')
api.add_resource(GetCloneDefaults, '/getCloneDefaults/<stack_name>')
api.add_resource(GetZDUCompatibility, '/getZDUCompatibility/<region>/<stack_name>')
api.add_resource(GetChangeSetDetails, '/getChangeSetDetails/<region>/<stack_name>/<change_set_name>')
api.add_resource(HasTerminationProtection, '/hasTerminationProtection/<region>/<stack_name>')


# Helpers
api.add_resource(GetEbsSnapshots, '/getEbsSnapshots/<region>/<stack_name>')
api.add_resource(GetRdsSnapshots, '/getRdsSnapshots/<region>/<stack_name>')
api.add_resource(GetTemplates, '/getTemplates/<template_type>')
api.add_resource(GetTemplateRepos, '/getTemplateRepos')
api.add_resource(GetVpcs, '/getVpcs/<region>')
api.add_resource(GetAllSubnetsForRegion, '/getAllSubnetsForRegion/<region>')
api.add_resource(GetSubnetsForVpc, '/getSubnetsForVpc/<region>/<vpc>')
api.add_resource(GetLockedStacks, '/getLockedStacks')
api.add_resource(GetKmsKeys, '/getKmsKeys/<region>/')
api.add_resource(GetSslCerts, '/getSslCerts/<region>/')
api.add_resource(SetStackLocking, '/setStackLocking/<lock>')

# Git
api.add_resource(GetGitBranch, '/getGitBranch/<template_repo>')
api.add_resource(GetGitCommitDifference, '/getGitCommitDifference/<template_repo>')
api.add_resource(DoGitPull, '/doGitPull/<template_repo>/<stack_name>')
api.add_resource(GetGitRevision, '/getGitRevision/<template_repo>')

# Restart Forge
api.add_resource(DoForgeRestart, '/doForgeRestart/<stack_name>')

# Status endpoint
api.add_resource(ForgeStatus, '/status')

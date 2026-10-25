// GitHub Branch Source schedules this Multibranch Pipeline from push webhooks.
// Configure branch discovery to include main only; see ci/README.md.
pipeline {
  agent any
  options {
    disableConcurrentBuilds()
    skipDefaultCheckout(true)
    timestamps()
    timeout(time: 120, unit: 'MINUTES')
  }
  parameters {
    string(name: 'CODEBUILD_PROJECT', defaultValue: 'webtech-shared-image-builder')
    string(name: 'AWS_CREDENTIALS_ID', defaultValue: 'jenkins-aws', description: 'Jenkins AWS credential ID')
    string(name: 'REPORT_BUCKET', defaultValue: 'webtech-shared-reports-671662643382')
    string(name: 'STAGING_CLUSTER', defaultValue: 'webtech-staging')
    string(name: 'STAGING_FRONTEND_SERVICE', defaultValue: 'webtech-staging-frontend')
    string(name: 'STAGING_BACKEND_SERVICE', defaultValue: 'webtech-staging-backend')
    string(name: 'STAGING_URL', defaultValue: '', description: 'Staging CloudFront HTTPS URL')
    string(name: 'STAGING_APPROVERS', defaultValue: '', description: 'Comma-separated Jenkins users or groups allowed to approve staging')
  }
  environment {
    AWS_DEFAULT_REGION = 'eu-west-2'
  }
  stages {
    stage('Checkout main') {
      when { branch 'main' }
      steps {
        deleteDir()
        checkout scm
        script { env.RELEASE_SHA = sh(script: 'git rev-parse HEAD', returnStdout: true).trim() }
      }
    }
    stage('Verify build configuration') {
      when { branch 'main' }
      steps { sh 'python3 ci/jenkins-release.py config' }
    }
    stage('CodeBuild: build, scan, publish') {
      when { branch 'main' }
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: (params.AWS_CREDENTIALS_ID ?: 'jenkins-aws')]]) {
          sh 'aws sts get-caller-identity'
          sh 'python3 ci/jenkins-release.py build'
        }
        // Publish scan evidence before waiting for approval.
        archiveArtifacts artifacts: 'codebuild-id.txt,release.json,reports/*.html,reports/*.json'
      }
    }
    stage('Approve staging deployment') {
      when { branch 'main' }
      steps {
        sh 'python3 ci/jenkins-release.py staging-config'
        script {
          env.STAGING_DEPLOYMENT_STATUS = 'AWAITING_APPROVAL'
          def release = readFile('release.json')
          echo "Images published for ${env.RELEASE_SHA}. Review this build's archived scan reports."
          timeout(time: 30, unit: 'MINUTES') {
            def decision = input(
              id: 'approve-staging',
              message: "Deploy commit ${env.RELEASE_SHA} to ${params.STAGING_CLUSTER}?\nURL: ${params.STAGING_URL}\nImages:\n${release}",
              ok: 'Deploy to staging',
              submitter: params.STAGING_APPROVERS.trim(),
              submitterParameter: 'STAGING_APPROVER'
            )
            env.STAGING_APPROVER = (decision instanceof Map ? decision['STAGING_APPROVER'] : decision).toString()
          }
          env.STAGING_APPROVED_AT = sh(script: 'date -u +%Y-%m-%dT%H:%M:%SZ', returnStdout: true).trim()
          env.STAGING_DEPLOYMENT_STATUS = 'APPROVED'
          writeFile file: 'staging-approval.txt', text: """Commit: ${env.RELEASE_SHA}
Approved by: ${env.STAGING_APPROVER}
Approved at (UTC): ${env.STAGING_APPROVED_AT}
Cluster: ${params.STAGING_CLUSTER}
URL: ${params.STAGING_URL}
Build: ${env.BUILD_URL}
Release manifest:
${release}
"""
          archiveArtifacts artifacts: 'staging-approval.txt'
          echo "Staging deployment approved by ${env.STAGING_APPROVER} for ${env.RELEASE_SHA}"
        }
      }
    }
    stage('Deploy and verify staging') {
      when { branch 'main' }
      steps {
        script { env.STAGING_DEPLOYMENT_STATUS = 'DEPLOYING' }
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: (params.AWS_CREDENTIALS_ID ?: 'jenkins-aws')]]) {
          sh 'aws sts get-caller-identity'
          sh 'bash ci/deploy.sh STAGING'
        }
        script { env.STAGING_DEPLOYMENT_STATUS = 'VERIFIED' }
      }
      post {
        unsuccessful {
          script { env.STAGING_DEPLOYMENT_STATUS = 'FAILED_OR_ABORTED' }
        }
      }
    }
  }
  post {
    always {
      script {
        if (env.RELEASE_SHA) {
          writeFile file: 'staging-result.txt', text: """Commit: ${env.RELEASE_SHA}
Pipeline result: ${currentBuild.currentResult}
Staging status: ${env.STAGING_DEPLOYMENT_STATUS ?: 'NOT_STARTED'}
Approved by: ${env.STAGING_APPROVER ?: 'NOT_APPROVED'}
Cluster: ${params.STAGING_CLUSTER}
Build: ${env.BUILD_URL}
"""
        }
      }
      archiveArtifacts artifacts: 'codebuild-id.txt,release.json,reports/*.html,reports/*.json,staging-approval.txt,staging-result.txt', allowEmptyArchive: true
    }
  }
}

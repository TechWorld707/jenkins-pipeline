// GitHub Branch Source schedules this Multibranch Pipeline from push webhooks.
// Configure branch discovery to include main only; see ci/README.md.
pipeline {
  agent any
  options {
    disableConcurrentBuilds()
    skipDefaultCheckout(true)
    timestamps()
    timeout(time: 180, unit: 'MINUTES')
  }
  parameters {
    booleanParam(name: 'BUILD_ONLY', defaultValue: false, description: 'Build, scan and publish images without deploying; use to bootstrap new infrastructure')
    string(name: 'CODEBUILD_PROJECT', defaultValue: 'webtech-shared-image-builder')
    string(name: 'AWS_CREDENTIALS_ID', defaultValue: 'jenkins-aws', description: 'Jenkins AWS credential ID')
    string(name: 'REPORT_BUCKET', defaultValue: 'webtech-shared-reports-671662643382')
    string(name: 'STAGING_CLUSTER', defaultValue: 'webtech-staging')
    string(name: 'STAGING_FRONTEND_SERVICE', defaultValue: 'webtech-staging-frontend')
    string(name: 'STAGING_BACKEND_SERVICE', defaultValue: 'webtech-staging-backend')
    string(name: 'STAGING_URL', defaultValue: '', description: 'Staging CloudFront HTTPS URL')
    string(name: 'STAGING_APPROVERS', defaultValue: '', description: 'Comma-separated Jenkins users or groups allowed to approve staging')
    string(name: 'PRODUCTION_CLUSTER', defaultValue: 'webtech-production')
    string(name: 'PRODUCTION_FRONTEND_SERVICE', defaultValue: 'webtech-production-frontend')
    string(name: 'PRODUCTION_BACKEND_SERVICE', defaultValue: 'webtech-production-backend')
    string(name: 'PRODUCTION_URL', defaultValue: '', description: 'Production CloudFront HTTPS URL')
    string(name: 'PRODUCTION_APPROVERS', defaultValue: '', description: 'Comma-separated Jenkins users or groups allowed to approve production')
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
      steps {
        sh 'python3 ci/jenkins-release.py config'
        // Fail before publishing immutable tags if deployment settings are missing.
        script {
          if (!params.BUILD_ONLY) {
            sh 'python3 ci/jenkins-release.py staging-config'
            sh 'python3 ci/jenkins-release.py production-config'
          }
        }
      }
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
      when { allOf { branch 'main'; expression { !params.BUILD_ONLY } } }
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
      when { allOf { branch 'main'; expression { !params.BUILD_ONLY } } }
      steps {
        script { env.STAGING_DEPLOYMENT_STATUS = 'DEPLOYING' }
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: (params.AWS_CREDENTIALS_ID ?: 'jenkins-aws')]]) {
          sh 'aws sts get-caller-identity'
          sh 'bash ci/deploy.sh STAGING'
        }
        script {
          env.STAGING_DEPLOYMENT_STATUS = 'VERIFIED'
          env.STAGING_RELEASE_HASH = sh(script: 'sha256sum release.json', returnStdout: true).trim().split()[0]
        }
      }
      post {
        success {
          writeFile file: 'staging-verification.txt', text: "Staging VERIFIED for ${env.RELEASE_SHA}\nURL: ${params.STAGING_URL}\nRelease manifest SHA256: ${env.STAGING_RELEASE_HASH}\n"
          archiveArtifacts artifacts: 'staging-verification.txt'
        }
        unsuccessful {
          script { env.STAGING_DEPLOYMENT_STATUS = 'FAILED_OR_ABORTED' }
        }
      }
    }
    stage('Approve production deployment') {
      when { allOf { branch 'main'; expression { !params.BUILD_ONLY } } }
      steps {
        sh 'python3 ci/jenkins-release.py production-config'
        sh 'python3 ci/jenkins-release.py production-ready'
        script {
          env.PRODUCTION_DEPLOYMENT_STATUS = 'AWAITING_APPROVAL'
          def release = readFile('release.json')
          echo "Staging verified for ${env.RELEASE_SHA}. Review the scan reports and staging verification artifact."
          timeout(time: 30, unit: 'MINUTES') {
            def decision = input(
              id: 'approve-production',
              message: "Deploy commit ${env.RELEASE_SHA} to ${params.PRODUCTION_CLUSTER}?\nURL: ${params.PRODUCTION_URL}\nImages:\n${release}",
              ok: 'Deploy to production',
              submitter: params.PRODUCTION_APPROVERS.trim(),
              submitterParameter: 'PRODUCTION_APPROVER'
            )
            env.PRODUCTION_APPROVER = (decision instanceof Map ? decision['PRODUCTION_APPROVER'] : decision).toString()
          }
          env.PRODUCTION_APPROVED_AT = sh(script: 'date -u +%Y-%m-%dT%H:%M:%SZ', returnStdout: true).trim()
          env.PRODUCTION_DEPLOYMENT_STATUS = 'APPROVED'
          writeFile file: 'production-approval.txt', text: """Commit: ${env.RELEASE_SHA}
Approved by: ${env.PRODUCTION_APPROVER}
Approved at (UTC): ${env.PRODUCTION_APPROVED_AT}
Cluster: ${params.PRODUCTION_CLUSTER}
URL: ${params.PRODUCTION_URL}
Build: ${env.BUILD_URL}
Release manifest:
${release}
"""
          archiveArtifacts artifacts: 'production-approval.txt'
          echo "Production deployment approved by ${env.PRODUCTION_APPROVER} for ${env.RELEASE_SHA}"
        }
      }
    }
    stage('Deploy and verify production') {
      when { allOf { branch 'main'; expression { !params.BUILD_ONLY } } }
      steps {
        sh 'python3 ci/jenkins-release.py production-ready'
        script { env.PRODUCTION_DEPLOYMENT_STATUS = 'DEPLOYING' }
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: (params.AWS_CREDENTIALS_ID ?: 'jenkins-aws')]]) {
          sh 'aws sts get-caller-identity'
          sh 'bash ci/deploy.sh PRODUCTION'
        }
        script { env.PRODUCTION_DEPLOYMENT_STATUS = 'VERIFIED' }
      }
      post {
        unsuccessful {
          script { env.PRODUCTION_DEPLOYMENT_STATUS = 'FAILED_OR_ABORTED' }
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
          writeFile file: 'production-result.txt', text: """Commit: ${env.RELEASE_SHA}
Pipeline result: ${currentBuild.currentResult}
Production status: ${env.PRODUCTION_DEPLOYMENT_STATUS ?: 'NOT_STARTED'}
Approved by: ${env.PRODUCTION_APPROVER ?: 'NOT_APPROVED'}
Cluster: ${params.PRODUCTION_CLUSTER}
Build: ${env.BUILD_URL}
"""
        }
      }
      archiveArtifacts artifacts: 'codebuild-id.txt,release.json,reports/*.html,reports/*.json,staging-approval.txt,staging-verification.txt,staging-result.txt,production-approval.txt,production-result.txt', allowEmptyArchive: true
    }
  }
}

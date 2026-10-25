pipeline {
  agent any
  options {
    disableConcurrentBuilds()
    skipDefaultCheckout(true)
    timestamps()
    timeout(time: 120, unit: 'MINUTES')
  }
  parameters {
    string(name: 'CODEBUILD_PROJECT', defaultValue: 'webtech-image-builder')
    string(name: 'REPORT_BUCKET', defaultValue: 'webtech-alb-logs-671662643382')
    string(name: 'STAGING_CLUSTER', defaultValue: '')
    string(name: 'STAGING_FRONTEND_SERVICE', defaultValue: '')
    string(name: 'STAGING_BACKEND_SERVICE', defaultValue: '')
    string(name: 'STAGING_URL', defaultValue: '')
    string(name: 'PRODUCTION_CLUSTER', defaultValue: '')
    string(name: 'PRODUCTION_FRONTEND_SERVICE', defaultValue: '')
    string(name: 'PRODUCTION_BACKEND_SERVICE', defaultValue: '')
    string(name: 'PRODUCTION_URL', defaultValue: '')
    string(name: 'PRODUCTION_APPROVERS', defaultValue: '')
  }
  environment {
    AWS_DEFAULT_REGION = 'eu-west-2'
    GITHUB_REPOSITORY = 'TechWorld707/jenkins-pipeline'
  }
  stages {
    stage('Checkout main') {
      when { branch 'main' }
      steps {
        checkout scm
        script { env.RELEASE_SHA = sh(script: 'git rev-parse HEAD', returnStdout: true).trim() }
      }
    }
    stage('Verify configuration and GitHub checks') {
      when { branch 'main' }
      steps {
        sh 'python3 ci/jenkins-release.py config'
        withCredentials([string(credentialsId: 'github-checks-token', variable: 'GH_TOKEN')]) {
          sh 'python3 ci/jenkins-release.py github'
        }
      }
    }
    stage('CodeBuild: build, scan, publish') {
      when { branch 'main' }
      steps { sh 'python3 ci/jenkins-release.py build' }
    }
    stage('Deploy and test staging') {
      when { branch 'main' }
      steps { sh 'python3 ci/deploy-ecs.py STAGING' }
    }
    stage('Approve production') {
      when { branch 'main' }
      steps {
        timeout(time: 30, unit: 'MINUTES') {
          script {
            input message: "Promote verified image digests for ${env.RELEASE_SHA}?",
                  submitter: params.PRODUCTION_APPROVERS
          }
        }
      }
    }
    stage('Promote and test production') {
      when { branch 'main' }
      steps { sh 'python3 ci/deploy-ecs.py PRODUCTION' }
    }
  }
  post {
    always {
      archiveArtifacts artifacts: 'release.json,reports/*.html,reports/*.json', allowEmptyArchive: true
    }
  }
}

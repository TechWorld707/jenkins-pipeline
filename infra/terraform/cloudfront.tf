provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

variable "cloudfront_origin_token" {
  description = "Random shared origin header value; supply through TF_VAR_cloudfront_origin_token."
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^[A-Za-z0-9_-]{32,128}$", var.cloudfront_origin_token))
    error_message = "Use a random 32-128 character token containing letters, digits, underscores or hyphens."
  }
}

data "aws_ec2_managed_prefix_list" "cloudfront_origin_facing" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

resource "aws_wafv2_web_acl" "frontend" {
  provider = aws.us_east_1
  name     = "webtech-cloudfront-waf"
  scope    = "CLOUDFRONT"

  default_action {
    allow {}
  }

  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 1
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedRulesCommonRuleSet"
      sampled_requests_enabled   = true
    }
  }
  rule {
    name     = "AWSManagedRulesKnownBadInputsRuleSet"
    priority = 2
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedRulesKnownBadInputsRuleSet"
      sampled_requests_enabled   = true
    }
  }
  rule {
    name     = "AWSManagedRulesAmazonIpReputationList"
    priority = 3
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesAmazonIpReputationList"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedRulesAmazonIpReputationList"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedRulesAnonymousIpList"
    priority = 4
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesAnonymousIpList"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedRulesAnonymousIpList"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "webtech-cloudfront-waf"
    sampled_requests_enabled   = true
  }
}

resource "aws_cloudfront_distribution" "frontend" {
  # checkov:skip=CKV_AWS_86:Access-log storage is deferred for this learning distribution; WAF metrics and request samples are enabled.
  # checkov:skip=CKV_AWS_310:Origin failover is deferred; this learning environment has one ALB origin.
  # checkov:skip=CKV_AWS_174:Uses the default CloudFront certificate without a custom domain; custom-certificate TLS policy is not applicable.
  # checkov:skip=CKV_AWS_374:Worldwide access is intentional for this learning website; no geographic restriction is required.
  # checkov:skip=CKV2_AWS_42:Learning website uses the default CloudFront domain and certificate; no custom domain is configured.
  default_root_object = "index.html"
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "Webtech learning frontend"
  price_class         = "PriceClass_100"
  web_acl_id          = aws_wafv2_web_acl.frontend.arn

  origin {
    domain_name = aws_lb.frontend.dns_name
    origin_id   = "frontend-alb"
    custom_header {
      name  = "X-Origin-Verify"
      value = var.cloudfront_origin_token
    }
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    response_headers_policy_id = aws_cloudfront_response_headers_policy.frontend.id
    target_origin_id           = "frontend-alb"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    min_ttl                    = 0
    default_ttl                = 0
    max_ttl                    = 0
    # Forward sessions and API inputs without caching personalised responses.
    forwarded_values {
      query_string = true
      headers      = ["*"]
      cookies {
        forward = "all"
      }
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  depends_on = [aws_lb_listener_rule.cloudfront]
}

output "frontend_url" {
  description = "HTTPS website URL protected by WAF"
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

resource "aws_cloudfront_response_headers_policy" "frontend" {
  name = "webtech-security-headers"
  security_headers_config {
    content_type_options {
      override = true
    }
    frame_options {
      frame_option = "DENY"
      override     = true
    }
    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }
    strict_transport_security {
      include_subdomains         = true
      preload                    = true
      access_control_max_age_sec = 31536000
      override                   = true
    }
    xss_protection {
      protection = true
      mode_block = true
      override   = true
    }

  }
}

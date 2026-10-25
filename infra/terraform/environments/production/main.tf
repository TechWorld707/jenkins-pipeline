locals { name = "webtech-${var.environment}" }
module "network" {
  source     = "../../modules/network"
  name       = local.name
  cidr_block = var.cidr_block
  nat_per_az = var.environment == "production"
}
module "observability" {
  source         = "../../modules/observability"
  name           = local.name
  vpc_id         = module.network.vpc_id
  retention_days = var.retention_days
}
module "database" {
  source            = "../../modules/database"
  name              = local.name
  subnet_ids        = module.network.data_subnet_ids
  security_group_id = aws_security_group.app["database"].id
  multi_az          = var.multi_az
  retention_days    = var.retention_days
}
module "ingress" {
  source                  = "../../modules/ingress"
  providers               = { aws = aws, aws.us_east_1 = aws.us_east_1 }
  name                    = local.name
  vpc_id                  = module.network.vpc_id
  public_subnet_ids       = module.network.public_subnet_ids
  alb_security_group_id   = aws_security_group.app["alb"].id
  cloudfront_origin_token = var.cloudfront_origin_token
  retention_days          = var.retention_days
}
module "ecs" {
  source             = "../../modules/ecs"
  name               = local.name
  subnet_ids         = module.network.app_subnet_ids
  security_group_ids = { for k, v in aws_security_group.app : k => v.id }
  images             = var.images
  db_host            = module.database.host
  db_name            = module.database.name
  db_secret_arn      = module.database.secret_arn
  desired_count      = var.desired_count
  retention_days     = var.retention_days
  target_group_arn   = module.ingress.target_group_arn
  container_insights = var.environment == "production"
  depends_on         = [module.ingress, aws_vpc_security_group_egress_rule.https, aws_vpc_security_group_ingress_rule.internal]
}

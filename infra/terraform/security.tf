resource "aws_security_group" "alb" {
  # checkov:skip=CKV2_AWS_5:Network foundation only; attach this group when the load balancer is added.
  name        = "jenkins-pipeline-alb-sg"
  description = "Allow public HTTPS traffic to the load balancer"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTPS from the internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Send traffic to frontend tasks"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["10.0.10.0/24", "10.0.11.0/24"]
  }

  tags = {
    Name = "jenkins-pipeline-alb-sg"
  }
}

resource "aws_security_group" "frontend" {
  # checkov:skip=CKV2_AWS_5:Network foundation only; attach this group when the frontend service is added.
  name        = "jenkins-pipeline-frontend-sg"
  description = "Allow traffic from the load balancer to the frontend"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "HTTP from the load balancer"
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "Send API requests to backend tasks"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["10.0.10.0/24", "10.0.11.0/24"]
  }

  tags = {
    Name = "jenkins-pipeline-frontend-sg"
  }
}

resource "aws_security_group" "backend" {
  # checkov:skip=CKV2_AWS_5:Network foundation only; attach this group when the backend service is added.
  name        = "jenkins-pipeline-backend-sg"
  description = "Allow API traffic from the frontend to the backend"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "API requests from the frontend"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.frontend.id]
  }

  egress {
    description = "PostgreSQL traffic to the data subnets"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["10.0.20.0/24", "10.0.21.0/24"]
  }

  tags = {
    Name = "jenkins-pipeline-backend-sg"
  }
}

resource "aws_security_group" "database" {
  # checkov:skip=CKV2_AWS_5:Network foundation only; attach this group when the database is added.
  name        = "jenkins-pipeline-database-sg"
  description = "Allow PostgreSQL traffic only from the backend"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "PostgreSQL from the backend"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.backend.id]
  }

  egress = []

  tags = {
    Name = "jenkins-pipeline-database-sg"
  }
}

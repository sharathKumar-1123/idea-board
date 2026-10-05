# Cost-sensitive defaults (~$6-8/day). For high availability raise node counts,
# set single_nat_gateway = false, db_multi_az = true and db_deletion_protection = true.
name               = "idea-board"
environment        = "production"
region             = "us-east-1"
node_instance_type = "t3.small"
node_desired_size  = 2
db_instance_class  = "db.t3.micro"

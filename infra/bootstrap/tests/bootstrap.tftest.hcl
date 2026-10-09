mock_provider "aws" {}
override_resource {
  target          = aws_iam_openid_connect_provider.github[0]
  override_during = plan
  values          = { arn = "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com" }
}
override_data {
  target = data.aws_caller_identity.current
  values = { account_id = "123456789012" }
}
run "identity_and_state_guardrails" {
  command = plan
  assert {
    condition     = aws_ecr_repository.app.image_tag_mutability == "IMMUTABLE"
    error_message = "Release tags must not be overwritten."
  }
  assert {
    condition     = aws_s3_bucket_public_access_block.state.block_public_policy && aws_s3_bucket_public_access_block.state.restrict_public_buckets
    error_message = "State must never be public."
  }
  assert {
    condition     = jsondecode(aws_iam_role.github.assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:sub"] == "repo:Khanu123/devops-deployment-lab:environment:devops-lab"
    error_message = "Trust must be limited to this repository's deployment environment."
  }
  assert {
    condition     = jsondecode(aws_iam_role.github.assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com"
    error_message = "OIDC audience must be AWS STS."
  }
}

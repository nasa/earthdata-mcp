





















output "mcp_server_security_group_id" {
  description = "Security group ID for the MCP server"
  value       = aws_security_group.mcp_server.id
}

export interface Skill {
  skill_id: string
  name: string
  slug: string
  description: string
  content: string
  tags: string[]
  created_at: string
  updated_at: string
}

export interface PluginConfig {
  plugin_name: string
  env_vars: Record<string, string>
  enabled: boolean
}

export interface AgentDef {
  agent_id: string
  name: string
  slug: string
  description: string
  system_prompt: string
  skill_ids: string[]
  tools: Record<string, any>[]
  plugins: PluginConfig[]
  model: string
  max_tokens: number
  effort: string
  is_builtin: boolean
  created_at: string
  updated_at: string
}

export interface PipelineNode {
  node_id: string
  node_type: 'trigger' | 'agent' | 'output'
  agent_id: string
  position_x: number
  position_y: number
  label: string | null
  config: Record<string, any>
}

export interface PipelineEdge {
  edge_id: string
  source_node_id: string
  target_node_id: string
  condition: string | null
}

export interface PipelineDef {
  pipeline_id: string
  name: string
  description: string
  nodes: PipelineNode[]
  edges: PipelineEdge[]
  entry_node_id: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface PipelineRun {
  correlation_id: string
  task_id: string
  jira_issue_key?: string
  pipeline_id?: string
  status: string
  current_stage: string
  stages_completed: string[]
  started_at: string
  completed_at?: string
}

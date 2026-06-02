<template>
  <div class="flex h-full">
    <!-- Left panel -->
    <div class="w-64 border-r border-surface-lighter flex flex-col">
      <!-- Pipeline selector -->
      <div class="p-3 border-b border-surface-lighter">
        <div class="flex items-center justify-between mb-2">
          <h2 class="text-xs font-semibold text-gray-400 uppercase tracking-wide">Pipelines</h2>
          <button @click="createPipeline" class="px-2 py-1 bg-primary text-white text-xs rounded hover:bg-primary-dark">+ New</button>
        </div>
        <select v-model="selectedPipelineId" @change="loadPipeline" class="w-full bg-surface-lighter border border-surface-lighter rounded px-2 py-1.5 text-sm text-gray-200 focus:border-primary focus:outline-none">
          <option value="">Select a pipeline...</option>
          <option v-for="p in pipelineStore.pipelines" :key="p.pipeline_id" :value="p.pipeline_id">
            {{ p.name }} {{ p.is_active ? '(active)' : '' }}
          </option>
        </select>
      </div>

      <!-- Scrollable palette area -->
      <div class="flex-1 overflow-auto">
        <!-- I/O + Logic palette (collapsible) -->
        <div class="border-b border-surface-lighter">
          <button @click="showIO = !showIO" class="w-full p-3 flex items-center justify-between text-xs font-semibold text-gray-400 uppercase tracking-wide hover:text-gray-300">
            <span>I/O &amp; Logic</span>
            <span class="text-gray-600">{{ showIO ? '&#9660;' : '&#9654;' }}</span>
          </button>
          <div v-show="showIO" class="px-3 pb-3 space-y-1">
            <div draggable="true" @dragstart="onDragStartIO($event, 'trigger')"
              class="p-2 bg-green-600/10 border border-green-600/30 rounded-lg cursor-grab text-sm hover:bg-green-600/20 transition-colors">
              <div class="font-medium text-green-400">&#9889; Webhook Trigger</div>
              <div class="text-xs text-gray-500">HTTP entry point</div>
            </div>
            <div draggable="true" @dragstart="onDragStartIO($event, 'condition')"
              class="p-2 bg-yellow-600/10 border border-yellow-600/30 rounded-lg cursor-grab text-sm hover:bg-yellow-600/20 transition-colors">
              <div class="font-medium text-yellow-400">&#9670; If / Condition</div>
              <div class="text-xs text-gray-500">Branch on payload field</div>
            </div>
            <div draggable="true" @dragstart="onDragStartIO($event, 'output-webhook')"
              class="p-2 bg-orange-600/10 border border-orange-600/30 rounded-lg cursor-grab text-sm hover:bg-orange-600/20 transition-colors">
              <div class="font-medium text-orange-400">&#128640; Webhook Output</div>
              <div class="text-xs text-gray-500">POST result to URL</div>
            </div>
            <div draggable="true" @dragstart="onDragStartIO($event, 'output-slack')"
              class="p-2 bg-purple-600/10 border border-purple-600/30 rounded-lg cursor-grab text-sm hover:bg-purple-600/20 transition-colors">
              <div class="font-medium text-purple-400">&#128172; Slack Output</div>
              <div class="text-xs text-gray-500">Send Slack message</div>
            </div>
          </div>
        </div>

        <!-- Agent palette (collapsible) -->
        <div class="border-b border-surface-lighter">
          <button @click="showAgents = !showAgents" class="w-full p-3 flex items-center justify-between text-xs font-semibold text-gray-400 uppercase tracking-wide hover:text-gray-300">
            <span>Agents ({{ agentStore.agents.length }})</span>
            <span class="text-gray-600">{{ showAgents ? '&#9660;' : '&#9654;' }}</span>
          </button>
          <div v-show="showAgents" class="px-2 pb-2 space-y-1">
            <div
              v-for="agent in agentStore.agents"
              :key="agent.agent_id"
              draggable="true"
              @dragstart="onDragStartAgent($event, agent)"
              class="p-2.5 bg-surface-lighter rounded-lg cursor-grab text-sm hover:bg-primary/10 hover:border-primary/30 border border-transparent transition-colors"
            >
              <div class="font-medium text-gray-200">{{ agent.name }}</div>
              <div class="text-xs text-gray-500">{{ agent.slug }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Actions -->
      <div class="p-3 border-t border-surface-lighter space-y-2">
        <button @click="savePipeline" :disabled="!selectedPipelineId" class="w-full px-3 py-2 bg-primary text-white text-sm rounded hover:bg-primary-dark disabled:opacity-40 disabled:cursor-not-allowed">
          Save Pipeline
        </button>
        <div class="flex gap-2">
          <button @click="activatePipeline" :disabled="!selectedPipelineId" class="flex-1 px-2 py-1.5 bg-green-600/20 text-green-400 text-xs rounded hover:bg-green-600/40 disabled:opacity-40 disabled:cursor-not-allowed">
            Activate
          </button>
          <button @click="exportPipeline" :disabled="!selectedPipelineId" class="flex-1 px-2 py-1.5 bg-surface-lighter text-gray-400 text-xs rounded hover:text-gray-200 disabled:opacity-40 disabled:cursor-not-allowed">
            Export
          </button>
          <button @click="triggerImport" class="flex-1 px-2 py-1.5 bg-surface-lighter text-gray-400 text-xs rounded hover:text-gray-200">
            Import
          </button>
          <input ref="importFileInput" type="file" accept=".json" @change="importPipeline" class="hidden" />
        </div>
        <div class="border-t border-surface-lighter pt-2">
          <label class="block text-xs text-gray-400 mb-1">Input (optional)</label>
          <textarea
            v-model="executeInput"
            rows="3"
            placeholder="Type a prompt or paste data..."
            class="w-full bg-surface-lighter border border-surface-lighter rounded px-2 py-1.5 text-xs text-gray-200 font-mono focus:border-primary focus:outline-none resize-y"
          ></textarea>
          <button
            @click="executePipeline"
            :disabled="!selectedPipelineId || executing"
            class="w-full mt-1 px-3 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            <span v-if="executing" class="animate-spin">&#9696;</span>
            {{ executing ? 'Running...' : 'Execute' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Canvas -->
    <div class="flex-1 relative" @drop="onDrop" @dragover.prevent>
      <VueFlow
        v-model:nodes="nodes"
        v-model:edges="edges"
        @connect="onConnect"
        @edge-click="onEdgeClick"
        @keydown="onKeyDown"
        :default-viewport="{ zoom: 1, x: 50, y: 50 }"
        :default-edge-options="{ type: 'button', style: { strokeWidth: 2 }, interactionWidth: 20 }"
        :edges-updatable="true"
        :select-nodes-on-drag="false"
        fit-view-on-init
        class="h-full"
        tabindex="0"
      >
        <Background />
        <Controls />

        <!-- Custom edge with delete button on the line -->
        <template #edge-button="props">
          <BaseEdge
            :id="props.id"
            :path="getBezierPath({ sourceX: props.sourceX, sourceY: props.sourceY, sourcePosition: props.sourcePosition, targetX: props.targetX, targetY: props.targetY, targetPosition: props.targetPosition })[0]"
            :style="props.style"
            :marker-end="props.markerEnd"
          />
          <EdgeLabelRenderer>
            <div
              :style="{
                position: 'absolute',
                transform: `translate(-50%, -50%) translate(${(props.sourceX + props.targetX) / 2}px, ${(props.sourceY + props.targetY) / 2}px)`,
                pointerEvents: 'all',
              }"
              class="edge-button-container nodrag nopan"
            >
              <button class="edge-delete-btn" @click.stop="deleteEdgeById(props.id)">&times;</button>
              <span v-if="props.data?.condition" class="edge-condition-label">{{ props.data.condition }}</span>
            </div>
          </EdgeLabelRenderer>
        </template>
        <MiniMap :node-color="miniMapColor" :mask-color="'rgba(30, 30, 46, 0.8)'" style="background: #2a2a3e;" />

        <!-- Trigger node -->
        <template #node-trigger="nodeProps">
          <div class="node-wrapper">
            <button @click.stop="removeNode(nodeProps.id)" class="node-delete-btn">&times;</button>
            <div class="io-node trigger-node" @dblclick.stop="openSchemaEditor(nodeProps.id)">
              <div class="io-node-header">
                <span class="text-lg">&#9889;</span>
                <span class="io-node-name">{{ nodeProps.data.label }}</span>
              </div>
              <div class="text-xs text-gray-500 mt-1 break-all" v-if="selectedPipelineId">
                /api/pipelines/webhook/...
              </div>
              <div v-if="nodeProps.data.config?.output_schema?.length" class="schema-preview">
                <div class="schema-badge out">OUT</div>
                <span v-for="f in nodeProps.data.config.output_schema" :key="f.name" class="schema-field">{{ f.name }}<span class="schema-type">{{ f.type }}</span></span>
              </div>
              <Handle type="source" :position="Position.Right" />
            </div>
          </div>
        </template>

        <!-- Agent node -->
        <template #node-agent="nodeProps">
          <div class="node-wrapper">
            <button @click.stop="removeNode(nodeProps.id)" class="node-delete-btn">&times;</button>
            <div class="agent-node" @dblclick.stop="openSchemaEditor(nodeProps.id)">
              <Handle type="target" :position="Position.Left" />
              <div class="agent-node-header">
                <span class="text-base">&#129302;</span>
                <span class="agent-node-name">{{ nodeProps.data.label || nodeProps.data.agentName }}</span>
              </div>
              <div class="agent-node-model">{{ nodeProps.data.agentModel }}</div>
              <div v-if="nodeProps.data.config?.input_schema?.length || nodeProps.data.config?.output_schema?.length" class="schema-preview">
                <template v-if="nodeProps.data.config?.input_schema?.length">
                  <div class="schema-badge in">IN</div>
                  <span v-for="f in nodeProps.data.config.input_schema" :key="'i'+f.name" class="schema-field">{{ f.name }}<span class="schema-type">{{ f.type }}</span></span>
                </template>
                <template v-if="nodeProps.data.config?.output_schema?.length">
                  <div class="schema-badge out">OUT</div>
                  <span v-for="f in nodeProps.data.config.output_schema" :key="'o'+f.name" class="schema-field">{{ f.name }}<span class="schema-type">{{ f.type }}</span></span>
                </template>
              </div>
              <Handle type="source" :position="Position.Right" />
            </div>
          </div>
        </template>

        <!-- Condition (If) node -->
        <template #node-condition="nodeProps">
          <div class="node-wrapper">
            <button @click.stop="removeNode(nodeProps.id)" class="node-delete-btn">&times;</button>
            <div class="io-node condition-node" @dblclick.stop="openNodeConfig(nodeProps.id)">
              <Handle type="target" :position="Position.Left" />
              <div class="io-node-header">
                <span class="text-lg">&#9670;</span>
                <span class="io-node-name">{{ nodeProps.data.label }}</span>
              </div>
              <div class="text-xs text-gray-500 mt-1">
                {{ nodeProps.data.config?.field || 'field' }} {{ nodeProps.data.config?.operator || '==' }} {{ nodeProps.data.config?.value || '?' }}
              </div>
              <div class="condition-handles">
                <div class="condition-handle-label true-label">true</div>
                <div class="condition-handle-label false-label">false</div>
              </div>
              <Handle id="true" type="source" :position="Position.Right" :style="{ top: '35%' }" />
              <Handle id="false" type="source" :position="Position.Right" :style="{ top: '75%' }" />
            </div>
          </div>
        </template>

        <!-- Output node -->
        <template #node-output="nodeProps">
          <div class="node-wrapper">
            <button @click.stop="removeNode(nodeProps.id)" class="node-delete-btn">&times;</button>
            <div class="io-node output-node" @dblclick.stop="openNodeConfig(nodeProps.id)">
              <Handle type="target" :position="Position.Left" />
              <div class="io-node-header">
                <span class="text-lg">{{ nodeProps.data.outputType === 'slack' ? '&#128172;' : '&#128640;' }}</span>
                <span class="io-node-name">{{ nodeProps.data.label }}</span>
              </div>
              <div class="text-xs text-gray-500 mt-1">{{ nodeProps.data.outputType }}</div>
              <div v-if="nodeProps.data.config?.input_schema?.length" class="schema-preview">
                <div class="schema-badge in">IN</div>
                <span v-for="f in nodeProps.data.config.input_schema" :key="f.name" class="schema-field">{{ f.name }}<span class="schema-type">{{ f.type }}</span></span>
              </div>
            </div>
          </div>
        </template>
      </VueFlow>

      <!-- Pipeline name overlay -->
      <div v-if="selectedPipelineId" class="absolute top-3 left-3 z-10">
        <input
          v-model="pipelineName"
          class="bg-surface-light/90 backdrop-blur border border-surface-lighter rounded px-3 py-1.5 text-sm text-gray-200 focus:border-primary focus:outline-none"
          placeholder="Pipeline name"
        />
      </div>

      <!-- Webhook URL display -->
      <div v-if="selectedPipelineId" class="absolute top-3 right-3 z-10 bg-surface-light/90 backdrop-blur border border-surface-lighter rounded px-3 py-1.5">
        <div class="text-xs text-gray-400">Webhook URL</div>
        <code class="text-xs text-green-400 select-all">{{ webhookUrl }}</code>
      </div>
    </div>

    <!-- Schema editor panel (double-click) -->
    <div v-if="schemaNodeId" class="w-80 border-l border-surface-lighter p-4 space-y-4 overflow-auto">
      <div class="flex items-center justify-between">
        <h3 class="text-sm font-semibold text-gray-300">I/O Schema</h3>
        <button @click="schemaNodeId = null" class="text-gray-400 hover:text-gray-200 text-sm">Close</button>
      </div>
      <p class="text-xs text-gray-500">Define the input/output fields to standardize data between nodes.</p>

      <!-- Input schema -->
      <div v-if="schemaShowInput">
        <div class="flex items-center justify-between mb-2">
          <label class="text-xs font-semibold text-blue-400 uppercase">Input Fields</label>
          <button @click="addSchemaField('input')" class="text-xs text-gray-400 hover:text-gray-200">+ Add</button>
        </div>
        <div v-for="(field, i) in schemaInput" :key="'si'+i" class="flex items-center gap-1 mb-1.5">
          <input v-model="field.name" placeholder="name" class="flex-1 bg-surface-lighter border border-surface-lighter rounded px-2 py-1 text-xs text-gray-200 focus:border-primary focus:outline-none font-mono" />
          <select v-model="field.type" class="w-20 bg-surface-lighter border border-surface-lighter rounded px-1 py-1 text-xs text-gray-200 focus:border-primary focus:outline-none">
            <option value="string">string</option>
            <option value="boolean">bool</option>
            <option value="number">number</option>
            <option value="json">json</option>
            <option value="array">array</option>
          </select>
          <button @click="schemaInput.splice(i, 1)" class="text-red-400 text-xs hover:text-red-300 px-1">&times;</button>
        </div>
        <div v-if="!schemaInput.length" class="text-xs text-gray-600 italic">No input fields</div>
      </div>

      <!-- Output schema -->
      <div>
        <div class="flex items-center justify-between mb-2">
          <label class="text-xs font-semibold text-green-400 uppercase">Output Fields</label>
          <button @click="addSchemaField('output')" class="text-xs text-gray-400 hover:text-gray-200">+ Add</button>
        </div>
        <div v-for="(field, i) in schemaOutput" :key="'so'+i" class="flex items-center gap-1 mb-1.5">
          <input v-model="field.name" placeholder="name" class="flex-1 bg-surface-lighter border border-surface-lighter rounded px-2 py-1 text-xs text-gray-200 focus:border-primary focus:outline-none font-mono" />
          <select v-model="field.type" class="w-20 bg-surface-lighter border border-surface-lighter rounded px-1 py-1 text-xs text-gray-200 focus:border-primary focus:outline-none">
            <option value="string">string</option>
            <option value="boolean">bool</option>
            <option value="number">number</option>
            <option value="json">json</option>
            <option value="array">array</option>
          </select>
          <button @click="schemaOutput.splice(i, 1)" class="text-red-400 text-xs hover:text-red-300 px-1">&times;</button>
        </div>
        <div v-if="!schemaOutput.length" class="text-xs text-gray-600 italic">No output fields</div>
      </div>

      <!-- Description per field -->
      <div v-if="schemaInput.length || schemaOutput.length">
        <label class="block text-xs text-gray-400 mb-1">Field Descriptions</label>
        <div v-for="field in [...schemaInput, ...schemaOutput]" :key="'d'+field.name" class="flex items-center gap-1 mb-1">
          <span class="text-xs text-gray-400 font-mono w-20 truncate">{{ field.name }}</span>
          <input v-model="field.description" placeholder="description..." class="flex-1 bg-surface-lighter border border-surface-lighter rounded px-2 py-1 text-xs text-gray-300 focus:border-primary focus:outline-none" />
        </div>
      </div>

      <!-- Workspace access (agent nodes) -->
      <div v-if="schemaNodeType === 'agent'">
        <label class="text-xs font-semibold text-yellow-400 uppercase mb-2 block">Workspace</label>
        <select v-model="schemaWorkspaceAccess" class="w-full bg-surface-lighter border border-surface-lighter rounded px-3 py-2 text-sm text-gray-200 focus:border-primary focus:outline-none">
          <option value="none">No access</option>
          <option value="read">Read only</option>
          <option value="readwrite">Read / Write</option>
        </select>
        <p class="text-xs text-gray-600 mt-1">Agents with workspace access can read/write files in the shared Git repo.</p>
      </div>

      <!-- Repo config (trigger nodes) -->
      <div v-if="schemaNodeType === 'trigger'" class="space-y-3">
        <label class="text-xs font-semibold text-yellow-400 uppercase block">Repository</label>
        <div>
          <label class="block text-xs text-gray-400 mb-1">Repository URL (optional)</label>
          <input v-model="schemaRepoUrl" placeholder="https://github.com/org/repo" class="w-full bg-surface-lighter border border-surface-lighter rounded px-3 py-2 text-sm text-gray-200 focus:border-primary focus:outline-none" />
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1">Branch</label>
          <input v-model="schemaBranch" placeholder="main" class="w-full bg-surface-lighter border border-surface-lighter rounded px-3 py-2 text-sm text-gray-200 focus:border-primary focus:outline-none" />
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1">Git Token env var</label>
          <input v-model="schemaGitTokenVar" placeholder="GITHUB_TOKEN" class="w-full bg-surface-lighter border border-surface-lighter rounded px-3 py-2 text-sm text-gray-200 focus:border-primary focus:outline-none" />
          <p class="text-xs text-gray-600 mt-1">Name of environment variable containing the Git token.</p>
        </div>
      </div>

      <button @click="saveSchema" class="w-full px-3 py-2 bg-primary text-white text-sm rounded hover:bg-primary-dark">
        Save Schema
      </button>
    </div>

    <!-- Config panel -->
    <div v-if="configNodeId && !schemaNodeId" class="w-72 border-l border-surface-lighter p-4 space-y-4 overflow-auto">
      <div class="flex items-center justify-between">
        <h3 class="text-sm font-semibold text-gray-300">Node Config</h3>
        <button @click="configNodeId = null" class="text-gray-400 hover:text-gray-200 text-sm">Close</button>
      </div>

      <!-- Condition node config -->
      <template v-if="configNodeType === 'condition'">
        <div>
          <label class="block text-xs text-gray-400 mb-1">Field (payload key)</label>
          <input v-model="configData.field" placeholder="e.g. status, approved, score" class="w-full bg-surface-lighter border border-surface-lighter rounded px-3 py-2 text-sm text-gray-200 focus:border-primary focus:outline-none" />
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1">Operator</label>
          <select v-model="configData.operator" class="w-full bg-surface-lighter border border-surface-lighter rounded px-3 py-2 text-sm text-gray-200 focus:border-primary focus:outline-none">
            <option value="==">== (equals)</option>
            <option value="!=">!= (not equals)</option>
            <option value="contains">contains</option>
            <option value="exists">exists (field is truthy)</option>
            <option value=">">&#62; (greater than)</option>
            <option value="<">&#60; (less than)</option>
          </select>
        </div>
        <div v-if="configData.operator !== 'exists'">
          <label class="block text-xs text-gray-400 mb-1">Value</label>
          <input v-model="configData.value" placeholder="e.g. approved, true, 5" class="w-full bg-surface-lighter border border-surface-lighter rounded px-3 py-2 text-sm text-gray-200 focus:border-primary focus:outline-none" />
        </div>
        <div class="text-xs text-gray-500 bg-surface rounded p-2">
          <strong>True</strong> output: top-right handle<br>
          <strong>False</strong> output: bottom-right handle
        </div>
        <button @click="saveNodeConfig" class="w-full px-3 py-2 bg-primary text-white text-sm rounded hover:bg-primary-dark">
          Save Config
        </button>
      </template>

      <!-- Output node config -->
      <template v-if="configNodeType === 'output'">
        <div>
          <label class="block text-xs text-gray-400 mb-1">Output Type</label>
          <select v-model="configData.output_type" class="w-full bg-surface-lighter border border-surface-lighter rounded px-3 py-2 text-sm text-gray-200 focus:border-primary focus:outline-none">
            <option value="webhook">Webhook</option>
            <option value="slack">Slack</option>
          </select>
        </div>
        <template v-if="configData.output_type === 'webhook'">
          <div>
            <label class="block text-xs text-gray-400 mb-1">URL</label>
            <input v-model="configData.url" placeholder="https://example.com/callback" class="w-full bg-surface-lighter border border-surface-lighter rounded px-3 py-2 text-sm text-gray-200 focus:border-primary focus:outline-none" />
          </div>
        </template>
        <template v-if="configData.output_type === 'slack'">
          <div>
            <label class="block text-xs text-gray-400 mb-1">Slack Webhook URL</label>
            <input v-model="configData.slack_webhook_url" placeholder="https://hooks.slack.com/services/..." class="w-full bg-surface-lighter border border-surface-lighter rounded px-3 py-2 text-sm text-gray-200 focus:border-primary focus:outline-none" />
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1">Channel (optional)</label>
            <input v-model="configData.slack_channel" placeholder="#general" class="w-full bg-surface-lighter border border-surface-lighter rounded px-3 py-2 text-sm text-gray-200 focus:border-primary focus:outline-none" />
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1">Message Template</label>
            <textarea v-model="configData.slack_message_template" rows="3" placeholder="Pipeline {{correlation_id}} completed" class="w-full bg-surface-lighter border border-surface-lighter rounded px-3 py-2 text-sm text-gray-200 font-mono focus:border-primary focus:outline-none resize-y" />
          </div>
        </template>
        <button @click="saveNodeConfig" class="w-full px-3 py-2 bg-primary text-white text-sm rounded hover:bg-primary-dark">
          Save Config
        </button>
      </template>
    </div>

    <!-- Edge config panel -->
    <div v-if="selectedEdge && !configNodeId" class="w-64 border-l border-surface-lighter p-4">
      <h3 class="text-sm font-semibold text-gray-300 mb-3">Edge</h3>
      <div class="space-y-3">
        <div>
          <label class="block text-xs text-gray-400 mb-1">Condition (optional)</label>
          <input
            v-model="edgeCondition"
            placeholder="e.g. approved, failed"
            class="w-full bg-surface-lighter border border-surface-lighter rounded px-3 py-2 text-sm text-gray-200 focus:border-primary focus:outline-none"
          />
        </div>
        <button @click="updateEdgeCondition" class="w-full px-3 py-1.5 bg-primary text-white text-sm rounded hover:bg-primary-dark">
          Update
        </button>
        <button @click="deleteEdge" class="w-full px-3 py-1.5 bg-red-600/20 text-red-400 text-sm rounded hover:bg-red-600/40">
          Delete Edge
        </button>
        <button @click="selectedEdge = null" class="w-full px-3 py-1.5 text-gray-400 text-sm hover:text-gray-200">
          Close
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { VueFlow, type Node, type Edge, Position, Handle, BaseEdge, EdgeLabelRenderer, getBezierPath } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'
import { useAgentsStore } from '../stores/agents'
import { usePipelinesStore } from '../stores/pipelines'
import type { AgentDef } from '../types'

const agentStore = useAgentsStore()
const pipelineStore = usePipelinesStore()

const selectedPipelineId = ref('')
const pipelineName = ref('')
const nodes = ref<Node[]>([])
const edges = ref<Edge[]>([])
const selectedEdge = ref<Edge | null>(null)
const edgeCondition = ref('')
const configNodeId = ref<string | null>(null)
const configNodeType = ref('')
const configData = ref<Record<string, any>>({})
const schemaNodeId = ref<string | null>(null)
const schemaNodeType = ref('')
const schemaShowInput = ref(true)
const schemaInput = ref<{ name: string; type: string; description: string }[]>([])
const schemaOutput = ref<{ name: string; type: string; description: string }[]>([])
const showIO = ref(false)
const showAgents = ref(true)
const executeInput = ref('')
const importFileInput = ref<HTMLInputElement | null>(null)
const executing = ref(false)
const schemaWorkspaceAccess = ref('none')
const schemaRepoUrl = ref('')
const schemaBranch = ref('main')
const schemaGitTokenVar = ref('')

const webhookUrl = computed(() => {
  if (!selectedPipelineId.value) return ''
  return `${window.location.origin}/api/pipelines/webhook/${selectedPipelineId.value}`
})

function miniMapColor(node: Node) {
  if (node.type === 'trigger') return '#22c55e'
  if (node.type === 'output') return '#f97316'
  if (node.type === 'condition') return '#eab308'
  return '#667eea'
}

onMounted(async () => {
  await Promise.all([agentStore.fetchAll(), pipelineStore.fetchAll()])
  if (pipelineStore.pipelines.length && !selectedPipelineId.value) {
    selectedPipelineId.value = pipelineStore.pipelines[0].pipeline_id
    await loadPipeline()
  }
})

// --- Drag & Drop ---

function onDragStartAgent(event: DragEvent, agent: AgentDef) {
  event.dataTransfer?.setData('application/nodetype', 'agent')
  event.dataTransfer?.setData('application/agent', JSON.stringify(agent))
}

function onDragStartIO(event: DragEvent, ioType: string) {
  event.dataTransfer?.setData('application/nodetype', ioType)
}

function onDrop(event: DragEvent) {
  const nodeType = event.dataTransfer?.getData('application/nodetype')
  if (!nodeType) return

  const canvas = (event.target as HTMLElement).closest('.vue-flow')
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const position = { x: event.clientX - rect.left - 80, y: event.clientY - rect.top - 30 }
  const nodeId = `node-${Date.now()}`

  if (nodeType === 'trigger') {
    if (nodes.value.some(n => n.type === 'trigger')) { alert('Only one trigger node allowed'); return }
    nodes.value = [...nodes.value, {
      id: nodeId, type: 'trigger', position,
      data: { label: 'Webhook Trigger', nodeType: 'trigger', config: {} },
    }]
  } else if (nodeType === 'condition') {
    nodes.value = [...nodes.value, {
      id: nodeId, type: 'condition', position,
      data: { label: 'If', nodeType: 'condition', config: { field: '', operator: '==', value: '' } },
    }]
  } else if (nodeType === 'output-webhook') {
    nodes.value = [...nodes.value, {
      id: nodeId, type: 'output', position,
      data: { label: 'Webhook Output', nodeType: 'output', outputType: 'webhook', config: { output_type: 'webhook', url: '' } },
    }]
  } else if (nodeType === 'output-slack') {
    nodes.value = [...nodes.value, {
      id: nodeId, type: 'output', position,
      data: { label: 'Slack Output', nodeType: 'output', outputType: 'slack', config: { output_type: 'slack', slack_webhook_url: '', slack_channel: '', slack_message_template: 'Pipeline {{correlation_id}} completed' } },
    }]
  } else if (nodeType === 'agent') {
    const agentRaw = event.dataTransfer?.getData('application/agent')
    if (!agentRaw) return
    const agent: AgentDef = JSON.parse(agentRaw)
    nodes.value = [...nodes.value, {
      id: nodeId, type: 'agent', position,
      data: { agentId: agent.agent_id, agentName: agent.name, agentSlug: agent.slug, agentModel: agent.model, label: agent.name, nodeType: 'agent', config: {} },
    }]
  }
}

// --- Edges ---

function onConnect(params: any) {
  const handle = params.sourceHandle
  edges.value = [...edges.value, {
    id: `edge-${Date.now()}`,
    type: 'button',
    source: params.source,
    target: params.target,
    sourceHandle: handle,
    targetHandle: params.targetHandle,
    animated: true,
    data: { condition: handle === 'true' || handle === 'false' ? handle : null, sourceHandle: handle },
    style: handle === 'true' ? { stroke: '#22c55e', strokeWidth: 2 } : handle === 'false' ? { stroke: '#ef4444', strokeWidth: 2 } : { strokeWidth: 2 },
  }]
}

function onEdgeClick(_: MouseEvent, edge: Edge) {
  selectedEdge.value = edge
  edgeCondition.value = edge.data?.condition || ''
  configNodeId.value = null

  // Highlight the selected edge
  edges.value = edges.value.map(e => ({
    ...e,
    selected: e.id === edge.id,
  }))
}

function onKeyDown(event: KeyboardEvent) {
  if (event.key === 'Delete' || event.key === 'Backspace') {
    // Delete selected edges
    const selectedEdges = edges.value.filter(e => e.selected)
    if (selectedEdges.length) {
      edges.value = edges.value.filter(e => !e.selected)
      selectedEdge.value = null
      event.preventDefault()
      return
    }
    // Delete selected nodes
    const selectedNodes = nodes.value.filter(n => n.selected)
    if (selectedNodes.length) {
      const nodeIds = new Set(selectedNodes.map(n => n.id))
      nodes.value = nodes.value.filter(n => !n.selected)
      edges.value = edges.value.filter(e => !nodeIds.has(e.source) && !nodeIds.has(e.target))
      event.preventDefault()
    }
  }
}

function updateEdgeCondition() {
  if (!selectedEdge.value) return
  edges.value = edges.value.map(e => {
    if (e.id === selectedEdge.value!.id) {
      return { ...e, data: { ...e.data, condition: edgeCondition.value || null }, label: edgeCondition.value || e.label || '' }
    }
    return e
  })
  selectedEdge.value = null
}

function deleteEdgeById(edgeId: string) {
  edges.value = edges.value.filter(e => e.id !== edgeId)
  if (selectedEdge.value?.id === edgeId) selectedEdge.value = null
}

function deleteEdge() {
  if (!selectedEdge.value) return
  edges.value = edges.value.filter(e => e.id !== selectedEdge.value!.id)
  selectedEdge.value = null
}

// --- Node actions ---

function removeNode(nodeId: string) {
  nodes.value = nodes.value.filter(n => n.id !== nodeId)
  edges.value = edges.value.filter(e => e.source !== nodeId && e.target !== nodeId)
}

function openNodeConfig(nodeId: string) {
  const node = nodes.value.find(n => n.id === nodeId)
  if (!node) return
  configNodeId.value = nodeId
  configNodeType.value = node.type || ''
  configData.value = { ...(node.data.config || {}) }
  selectedEdge.value = null
  schemaNodeId.value = null
}

function openSchemaEditor(nodeId: string) {
  const node = nodes.value.find(n => n.id === nodeId)
  if (!node) return
  schemaNodeId.value = nodeId
  schemaNodeType.value = node.type || 'agent'
  configNodeId.value = null
  selectedEdge.value = null

  const cfg = node.data.config || {}
  schemaInput.value = JSON.parse(JSON.stringify(cfg.input_schema || []))
  schemaOutput.value = JSON.parse(JSON.stringify(cfg.output_schema || []))
  schemaWorkspaceAccess.value = cfg.workspace_access || 'none'
  schemaRepoUrl.value = cfg.repo_url || ''
  schemaBranch.value = cfg.branch || 'main'
  schemaGitTokenVar.value = cfg.git_token_var || ''

  schemaShowInput.value = node.type !== 'trigger'
}

function addSchemaField(direction: 'input' | 'output') {
  const list = direction === 'input' ? schemaInput : schemaOutput
  list.value.push({ name: '', type: 'string', description: '' })
}

function saveSchema() {
  if (!schemaNodeId.value) return
  nodes.value = nodes.value.map(n => {
    if (n.id === schemaNodeId.value) {
      const newConfig: Record<string, any> = {
        ...(n.data.config || {}),
        input_schema: schemaInput.value.filter(f => f.name.trim()),
        output_schema: schemaOutput.value.filter(f => f.name.trim()),
      }
      if (n.type === 'agent') {
        newConfig.workspace_access = schemaWorkspaceAccess.value
      }
      if (n.type === 'trigger') {
        newConfig.repo_url = schemaRepoUrl.value
        newConfig.branch = schemaBranch.value
        newConfig.git_token_var = schemaGitTokenVar.value
      }
      return {
        ...n,
        data: { ...n.data, config: newConfig },
      }
    }
    return n
  })
  schemaNodeId.value = null
}

function saveNodeConfig() {
  if (!configNodeId.value) return
  nodes.value = nodes.value.map(n => {
    if (n.id === configNodeId.value) {
      const newData = { ...n.data, config: { ...configData.value } }
      if (n.type === 'output') newData.outputType = configData.value.output_type || n.data.outputType
      if (n.type === 'condition') {
        newData.label = `If ${configData.value.field || 'field'} ${configData.value.operator || '=='} ${configData.value.operator === 'exists' ? '' : (configData.value.value || '?')}`.trim()
      }
      return { ...n, data: newData }
    }
    return n
  })
  configNodeId.value = null
}

// --- Pipeline CRUD ---

async function createPipeline() {
  const pipeline = await pipelineStore.create({ name: 'New Pipeline', description: '' })
  selectedPipelineId.value = pipeline.pipeline_id
  pipelineName.value = pipeline.name
  nodes.value = []
  edges.value = []
}

async function loadPipeline() {
  if (!selectedPipelineId.value) return
  await Promise.all([agentStore.fetchAll(), pipelineStore.fetchOne(selectedPipelineId.value)])
  const p = pipelineStore.current
  if (!p) return

  pipelineName.value = p.name

  nodes.value = p.nodes.map((n) => {
    const vfType = n.node_type || 'agent'

    if (vfType === 'trigger') {
      return {
        id: n.node_id, type: 'trigger',
        position: { x: n.position_x, y: n.position_y },
        data: { label: n.label || 'Webhook Trigger', nodeType: 'trigger', config: n.config || {} },
      }
    }

    if (vfType === 'condition') {
      const cfg = n.config || {}
      return {
        id: n.node_id, type: 'condition',
        position: { x: n.position_x, y: n.position_y },
        data: {
          label: n.label || `If ${cfg.field || 'field'} ${cfg.operator || '=='} ${cfg.value || '?'}`,
          nodeType: 'condition',
          config: cfg,
        },
      }
    }

    if (vfType === 'output') {
      return {
        id: n.node_id, type: 'output',
        position: { x: n.position_x, y: n.position_y },
        data: {
          label: n.label || 'Output',
          nodeType: 'output',
          outputType: n.config?.output_type || 'webhook',
          config: n.config || {},
        },
      }
    }

    const agentData = agentStore.agents.find(a => a.agent_id === n.agent_id)
    return {
      id: n.node_id, type: 'agent',
      position: { x: n.position_x, y: n.position_y },
      data: {
        agentId: n.agent_id,
        agentName: agentData?.name || 'Unknown',
        agentSlug: agentData?.slug || '',
        agentModel: agentData?.model || '',
        label: agentData?.name || n.label || 'Unknown',
        nodeType: 'agent',
        config: n.config || {},
      },
    }
  })

  edges.value = p.edges.map(e => ({
    id: e.edge_id,
    type: 'button',
    source: e.source_node_id,
    target: e.target_node_id,
    sourceHandle: e.condition === 'true' || e.condition === 'false' ? e.condition : undefined,
    animated: true,
    data: { condition: e.condition, sourceHandle: e.condition },
    style: e.condition === 'true' ? { stroke: '#22c55e', strokeWidth: 2 } : e.condition === 'false' ? { stroke: '#ef4444', strokeWidth: 2 } : { strokeWidth: 2 },
  }))
}

async function savePipeline() {
  if (!selectedPipelineId.value) return

  const triggerNode = nodes.value.find(n => n.type === 'trigger')

  const pipelineNodes = nodes.value.map(n => ({
    node_id: n.id,
    node_type: n.type || 'agent',
    agent_id: n.data.agentId || '',
    position_x: n.position.x,
    position_y: n.position.y,
    label: n.data.label || null,
    config: n.data.config || {},
  }))

  const pipelineEdges = edges.value.map(e => ({
    edge_id: e.id,
    source_node_id: e.source,
    target_node_id: e.target,
    condition: e.data?.sourceHandle || e.data?.condition || null,
  }))

  await pipelineStore.update(selectedPipelineId.value, {
    name: pipelineName.value,
    nodes: pipelineNodes as any,
    edges: pipelineEdges as any,
    entry_node_id: triggerNode?.id || nodes.value[0]?.id || '',
  })

  alert('Pipeline saved!')
}

async function exportPipeline() {
  if (!selectedPipelineId.value) return
  await pipelineStore.fetchOne(selectedPipelineId.value)
  const p = pipelineStore.current
  if (!p) return

  const blob = new Blob([JSON.stringify(p, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${p.name.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

function triggerImport() {
  importFileInput.value?.click()
}

async function importPipeline(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return

  try {
    const text = await file.text()
    const data = JSON.parse(text)

    const imported = await pipelineStore.create({
      name: data.name ? `${data.name} (imported)` : 'Imported Pipeline',
      description: data.description || '',
      nodes: data.nodes || [],
      edges: data.edges || [],
      entry_node_id: data.entry_node_id || '',
    })

    await pipelineStore.fetchAll()
    selectedPipelineId.value = imported.pipeline_id
    await loadPipeline()
  } catch (e: any) {
    alert(`Import failed: ${e.message}`)
  }

  if (importFileInput.value) importFileInput.value.value = ''
}

async function activatePipeline() {
  if (!selectedPipelineId.value) return
  await pipelineStore.activate(selectedPipelineId.value)
}

async function executePipeline() {
  if (!selectedPipelineId.value) return
  executing.value = true
  try {
    const inputData: Record<string, any> = {}
    if (executeInput.value.trim()) {
      try {
        Object.assign(inputData, JSON.parse(executeInput.value))
      } catch {
        inputData.prompt = executeInput.value
      }
    }
    const result = await pipelineStore.execute(selectedPipelineId.value, inputData)
    alert(`Pipeline started: ${result.correlation_id}`)
  } catch (e: any) {
    alert(`Error: ${e.message}`)
  } finally {
    executing.value = false
  }
}
</script>

<style scoped>
/* Node wrapper — positions the delete button relative to the node */
.node-wrapper {
  @apply relative;
}

.node-delete-btn {
  @apply absolute -top-2.5 -right-2.5 z-10
    w-5 h-5 rounded-full
    bg-gray-600 hover:bg-red-500
    text-gray-300 hover:text-white
    text-xs leading-none
    flex items-center justify-center
    border border-gray-500 hover:border-red-400
    opacity-0 transition-all duration-150
    cursor-pointer shadow-md;
}

.node-wrapper:hover .node-delete-btn {
  @apply opacity-100;
}

/* Agent node */
.agent-node {
  @apply bg-surface-light border border-primary/30 rounded-xl px-4 py-3 min-w-[160px] shadow-lg;
}
.agent-node-header {
  @apply flex items-center gap-2 mb-1;
}
.agent-node-name {
  @apply text-sm font-semibold text-gray-200;
}
.agent-node-model {
  @apply text-xs text-gray-500;
}

/* I/O nodes */
.io-node {
  @apply rounded-xl px-4 py-3 min-w-[160px] shadow-lg;
}
.trigger-node {
  @apply bg-surface-light border border-green-500/40;
}
.condition-node {
  @apply bg-surface-light border border-yellow-500/40 min-h-[100px];
}
.output-node {
  @apply bg-surface-light border border-orange-500/40;
}
.io-node-header {
  @apply flex items-center gap-2;
}
.io-node-name {
  @apply text-sm font-semibold text-gray-200;
}
.io-node-actions {
  @apply flex items-center gap-2 mt-2;
}

/* Condition handles */
.condition-handles {
  @apply flex flex-col gap-3 absolute right-2 top-0 h-full justify-around py-3 pointer-events-none;
}
.condition-handle-label {
  @apply text-xs font-mono;
}
.true-label {
  @apply text-green-400;
}
.false-label {
  @apply text-red-400;
}

.config-btn {
  @apply px-2 py-0.5 text-xs rounded bg-surface-lighter text-gray-400 hover:text-gray-200;
}

/* Schema preview on nodes */
.schema-preview {
  @apply flex flex-wrap items-center gap-1 mt-2 pt-2 border-t border-surface-lighter;
}
.schema-badge {
  @apply px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider;
}
.schema-badge.in {
  @apply bg-blue-500/20 text-blue-400;
}
.schema-badge.out {
  @apply bg-green-500/20 text-green-400;
}
.schema-field {
  @apply px-1.5 py-0.5 bg-surface rounded text-[10px] text-gray-400 font-mono flex items-center gap-1;
}
.schema-type {
  @apply text-gray-600;
}

/* Edge delete button — rendered at the midpoint of each edge */
.edge-button-container {
  @apply flex items-center gap-1;
}

.edge-delete-btn {
  @apply w-5 h-5 rounded-full
    bg-gray-600 hover:bg-red-500
    text-gray-300 hover:text-white
    text-sm leading-none
    flex items-center justify-center
    border border-gray-500 hover:border-red-400
    cursor-pointer shadow-md
    transition-colors duration-150;
}

.edge-condition-label {
  @apply text-xs text-gray-400 bg-surface-light/90 px-1.5 py-0.5 rounded;
}
</style>

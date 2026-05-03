"""
Tests for tool_graph.py - Local Model Tool Call Graph

These tests import via the app package (not sys.path hack) because
tool_graph.py uses relative imports.
"""
import pytest
import sys
import os

# Add project root to path so we can import `app` as a package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.tool_graph import LocalToolGraph, ToolNode, NodeType


class TestToolGraph:
    """Test suite for LocalToolGraph"""

    def test_graph_initialization(self):
        """Test that graph initializes with default settings"""
        graph = LocalToolGraph(max_energy=100.0)

        assert graph.max_energy == 100.0
        assert graph.nodes == {}
        assert graph.start_node is None
        assert len(graph.tools_registry) > 0

    def test_base_tools_registered(self):
        """Test that base tools are registered on init"""
        graph = LocalToolGraph()

        expected_tools = [
            'search_knowledge',
            'check_device_state',
            'control_device',
            'get_weather',
            'set_reminder'
        ]

        for tool in expected_tools:
            assert tool in graph.tools_registry

    def test_register_custom_tool(self):
        """Test registering a custom tool"""
        graph = LocalToolGraph()

        async def custom_handler(state):
            return {'result': 'custom'}

        graph.register_tool(
            name='custom_tool',
            handler=custom_handler,
            description='A custom tool',
            energy_cost=5.0,
            required_params=['param1']
        )

        assert 'custom_tool' in graph.tools_registry
        assert graph.tools_registry['custom_tool']['energy_cost'] == 5.0
        assert graph.tools_registry['custom_tool']['required_params'] == ['param1']

    def test_add_node(self):
        """Test adding a node to the graph"""
        graph = LocalToolGraph()

        async def handler(state):
            return state

        node = ToolNode(
            name='test_node',
            node_type=NodeType.TOOL,
            handler=handler,
            energy_cost=2.0
        )

        graph.add_node(node)

        assert 'test_node' in graph.nodes
        assert graph.nodes['test_node'].energy_cost == 2.0

    def test_add_start_node(self):
        """Test that start node is tracked"""
        graph = LocalToolGraph()

        async def handler(state):
            return state

        node = ToolNode(
            name='start',
            node_type=NodeType.START,
            handler=handler
        )

        graph.add_node(node)
        assert graph.start_node == node

    def test_add_edge(self):
        """Test adding edges between nodes"""
        graph = LocalToolGraph()

        async def handler(state):
            return state

        node1 = ToolNode(name='node1', node_type=NodeType.TOOL, handler=handler)
        node2 = ToolNode(name='node2', node_type=NodeType.TOOL, handler=handler)

        graph.add_node(node1)
        graph.add_node(node2)
        graph.add_edge('node1', 'node2')

        assert 'node2' in graph.nodes['node1'].edges

    def test_add_edge_invalid_nodes(self):
        """Test that adding edge with invalid nodes raises error"""
        graph = LocalToolGraph()

        with pytest.raises(ValueError):
            graph.add_edge('nonexistent1', 'nonexistent2')

    def test_build_tool_calling_graph(self):
        """Test building the standard tool calling graph"""
        graph = LocalToolGraph()
        graph.build_tool_calling_graph()

        expected_nodes = [
            'analyze_intent',
            'select_tool',
            'execute_tool',
            'generate_response',
            'end'
        ]

        for node_name in expected_nodes:
            assert node_name in graph.nodes

        assert graph.start_node is not None
        assert graph.start_node.name == 'analyze_intent'


class TestToolNode:
    """Test suite for ToolNode"""

    def test_node_creation(self):
        """Test creating a tool node"""
        async def handler(state):
            return state

        node = ToolNode(
            name='test',
            node_type=NodeType.TOOL,
            handler=handler,
            energy_cost=3.0,
            description='Test node'
        )

        assert node.name == 'test'
        assert node.node_type == NodeType.TOOL
        assert node.energy_cost == 3.0
        assert node.description == 'Test node'


class TestNodeTypes:
    """Test different node types"""

    def test_node_type_enum(self):
        """Test NodeType enum values"""
        assert NodeType.START.value == 'start'
        assert NodeType.TOOL.value == 'tool'
        assert NodeType.LLM.value == 'llm'
        assert NodeType.CONDITION.value == 'condition'
        assert NodeType.END.value == 'end'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

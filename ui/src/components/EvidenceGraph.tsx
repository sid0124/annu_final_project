import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/auth-context';
import { motion, AnimatePresence } from 'framer-motion';
import { Edge, Node, useWorkflow } from 'react-flow-renderer';
import { Shield, Database, Check, XCircle, Info } from 'lucide-react';
import { useDispatch } from 'react-redux';
import { verifyClaim } from '../services/api';

export const EvidenceGraph = () => {
  const { user } = useAuth();
  const dispatch = useDispatch();
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeNode, setActiveNode] = useState(null);

  useEffect(() => {
    // In production, fetch from API
    const fetchGraph = async () => {
      // Mock data - replace with real API call
      const mockNodes = [
        { id: 'claim1', type: 'claim', data: { label: 'Transformers dominate NLP', confidence: 0.92 } },
        { id: 'claim2', type: 'claim', data: { label: 'RNNs are obsolete', confidence: 0.35 } },
        { id: 'claim3', type: 'claim', data: { label: 'Attention mechanism is key', confidence: 0.88 } },
      ];

      const mockEdges = [
        { id: 'e1', source: 'claim1', target: 'evidence1', type: 'SUPPORTS' },
        { id: 'e2', source: 'claim2', target: 'evidence2', type: 'CONTRADICTED' },
        { id: 'e3', source: 'claim3', target: 'evidence3', type: 'SUPPORTS' },
      ];

      setNodes(mockNodes);
      setEdges(mockEdges);
      setLoading(false);
    };

    fetchGraph();
  }, [user?.user_id]);

  if (loading) {
    return (
      <motion.div
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.95 }}
        className="flex items-center justify-center h-64 text-gray-400"
      >
        <svg className="w-12 h-12 animate-spin text-gray-500" viewBox="0 0 24 24">
          <circle
            cx="12"
            cy="12"
            r="10"
            strokeWidth="3"
            fill="none"
            strokeCurrentColor="currentColor"
          />
          <path
            fill="currentColor"
            d="M19.4 15a1.65 1.65 0 0 1-1.1 3.05 1.65 1.65 0 0 1-2.95-1.1 1.65 1.65 0 0 1-1.13-3.03 1.65 1.65 0 0 1 1.15-3.02 1.65 1.65 0 0 1 2.95 1.1 1.65 1.65 0 0 1 1.12 3.01zM9.83 9.63a5.16 5.16 0 0 1 3.39 1.73A5.14 5.14 0 0 1 4 9.87 5.17 5.17 0 0 1 9.83 3.63a1.07 1.07 0 0 1 1.48 0z"
          />
        </svg>
        <span>Loading evidence graph...</span>
      </motion.div>
    );
  }

  return (
    <section className="md:pt-8">
      <h2 className="text-xl font-medium text-gray-900 mb-6">
        <Database className="inline-block mr-2 h-4 w-4" />Evidence Graph
      </h2>

      <div className="relative">
        {loading ? (
          <motion.div
            className="flex items-center justify-center h-64 text-gray-400"
          >
            <span>Loading evidence graph...</span>
          </motion.div>
        ) : (
          <div
            className="relative w-full h-[500px] rounded-lg overflow-hidden border border var(--border)"
          >
            <div
              className="absolute inset-0"
              style={{
                background:
                  'linear-gradient(180deg, var(--bg-card) 0%, var(--bg) 100%)',
            }}
          >
            <Edge
              data={edges}
              type={({ type }) => {
                switch (type) {
                  case 'SUPPORTS':
                    return '#10b981';
                  case 'CONTRADICTED':
                    return '#ef4444';
                  case 'PARTIALLY_SUPPORTED':
                    return '#f59e0b';
                  default:
                    return '#6b7280';
                }
              }}
            />
            <Node
              data={nodes}
              type={({ type }) => type}
            />
          </div>
        </div>

        {/* Legend */}
        <div
          className="absolute bottom-4 left-4 bg-black/60 text-xs text-white px-3 py-2 rounded"
        >
          <div className="flex items-center gap-2">
            <span
              style={{ color: '#10b981' }}
              className="w-3 h-3 rounded"
            ></span>
            <span>SUPPORTS</span>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span
              style={{ color: '#ef4444' }}
              className="w-3 h-3 rounded"
            ></span>
            <span>CONTRADICTED</span>
          </div>
        </div>
      </div>

      {/* Active node details */}
      {activeNode && (
        <motion.div
          className="mt-8 p-6 rounded-lg bg-white/5 backdrop-blur"
        >
          <h3 className="font-medium text-gray-900">
            {activeNode.data.label}
          </h3>
          <p className="text-sm text-gray-400">
            Confidence: {activeNode.data.confidence}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            {'Confidence ' + (activeNode.data.confidence > 0.8 ? 'high' : activeNode.data.confidence > 0.5 ? 'medium' : 'low')}
          </p>
        </motion.div>
      )}

      {/* Unsupported claims badge */}
      {nodes.filter((n) => n.type === 'claim' && n.data.confidence < 0.5).length > 0 && (
        <motion.div
          className="mt-4 p-4 rounded-lg bg-red-500/10 border-l-4 border-red-500"
        >
          <p className="text-sm text-red-400">
            <AlertCircle className="inline-block mr-1 h-4 w-4" /> {nodes.filter((n) => n.type === 'claim' && n.data.confidence < 0.5).length} unsupported claims detected - consider verification
          </p>
        </motion.div>
      )}
    </section>
  );
};
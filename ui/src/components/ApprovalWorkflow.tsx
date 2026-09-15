import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/auth-context';
import { motion, AnimatePresence } from 'framer-motion';
import { Shield, CheckCircle, Clock, AlertCircle, User } from 'lucide-react';
import { useDispatch } from 'react-redux';
import { approve_approval, reject_approval } from '../services/api';

export const ApprovalWorkflow = () => {
  const { user, isAuthenticated } = useAuth();
  const dispatch = useDispatch();
  const [pendingApprovals, setPendingApprovals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [currentApproval, setCurrentApproval] = useState(null);

  useEffect(() => {
    // Listen for approval events from the task execution
    const checkApprovals = async () => {
      if (!user?.user_id) return;
      try {
        const response = await axios.get('/api/v1/approval/pending', {
          params: { user_role: user.role }
        });
        setPendingApprovals(response.data || []);
      } catch (error) {
        // Fallback to mock data if API fails
        const mockApprovals = [
          {
            id: '1',
            tool: 'python_sandbox',
            action: 'Execute statistical analysis',
            risk: 'medium',
            requestedBy: user?.full_name || 'Researcher',
            createdAt: '2 min ago',
          },
          {
            id: '2',
            tool: 'retriever',
            action: 'Search research papers',
            risk: 'low',
            requestedBy: user?.full_name || 'Researcher',
            createdAt: '10 min ago',
          },
        ];
        setPendingApprovals(mockApprovals);
      }
    };
    
    checkApprovals();
    const interval = setInterval(checkApprovals, 3000);
    return () => clearInterval(interval);
  }, [user?.user_id, user?.role]);

  if (!isAuthenticated) return null;

  const handleApprove = async (approvalId: string) => {
    setShowModal(false);
    setCurrentApproval(null);
    // In production, call API to approve
    await approve_approval(approvalId, user?.user_id || 'current_user', 'Approved for safe execution');
    setPendingApprovals((prev) => prev.filter((a) => a.id !== approvalId));
  };

  const handleReject = async (approvalId: string) => {
    setShowModal(false);
    setCurrentApproval(null);
    // In production, call API to reject
    await reject_approval(approvalId, user?.user_id || 'current_user', 'Risk outside scope');
    setPendingApprovals((prev) => prev.filter((a) => a.id !== approvalId));
  };

  if (pendingApprovals.length === 0) {
    return null;
  }

  return (
    <section className="mt-8">
      <h2 className="text-lg font-medium text-gray-900 mb-6">
        <Shield className="inline-block mr-2 h-4 w-4" />Approval Workflow
      </h2>

      {pendingApprovals.map((approval) => (
        <motion.div
          key={approval.id}
          variants={{
            hidden: { opacity: 0, y: 20 },
            visible: { opacity: 1, y: 0 },
          }}
          transition={{ delay: 0.1 }}
          className="p-6 rounded-lg border var(--border) mb-4"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="font-medium text-gray-900">
                {approval.tool} execution request
              </p>
              <p className="text-xs text-gray-500">{approval.action}</p>
              <p className="text-xs text-gray-400">{approval.createdAt}</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-orange-500">
                Risk: {approval.risk}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Action buttons */}
      {pendingApprovals.length > 0 && (
        <div className="mt-6 pt-6 border-t border var(--border)">
          <div className="flex gap-3">
            <button
              onClick={() => setShowModal((prev) => !prev)}
              className="btn btn-outline"
            >
              Review Approvals
            </button>
          </div>

          {/* Modal */}
          {showModal && currentApproval && (
            <motion.div
              className="fixed inset-0 bg-black/50 backdrop-blur z-50 flex items-center justify-center"
            >
              <motion.div
                className="bg-white rounded-lg p-8 max-w-sm w-full shadow-2xl"
                variants={{
                  hidden: { scale: 0.95, opacity: 0 },
                  visible: { scale: 1, opacity: 1 },
                }}
                transition={{ type: 'spring', stiffness: 300, damping: 30 }}
              >
                <h3 className="font-medium text-gray-900 mb-4">
                  Approve Action: {currentApproval.tool}
                </h3>
                <p className="text-sm text-gray-500 mb-6">
                  Risk Level: {currentApproval.risk}
                </p>

                <div className="flex gap-3 mt-6">
                  <button
                    onClick={() => handleApprove(currentApproval.id)}
                    className="btn btn-primary flex-1"
                  >
                    <CheckCircle className="mr-2 h-4 w-4" /> Approve
                  </button>
                  <button
                    onClick={() => handleReject(currentApproval.id)}
                    className="btn btn-outline flex-1"
                  >
                    <AlertCircle className="mr-2 h-4 w-4" /> Reject
                  </button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </div>
      )}
    </section>
  );
};
import React, { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from './styles';
import { useAuth } from '../context/auth-context';
import { useDispatch } from 'react-redux';
import { logout } from '../store';
import { PieChart, BarChart, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { motion, AnimatePresence } from 'framer-motion';
import { Shield, Database, Code, Search, Calendar, AlertCircle, Clock } from 'lucide-react';

export const Dashboard = () => {
  const { user, isAuthenticated, login, logout } = useAuth();
  const dispatch = useDispatch();

  // State for animations
  const [loaded, setLoaded] = useState(false);
  const [safetyEvents, setSafetyEvents] = useState([]);
  const [metrics, setMetrics] = useState({
    taskSuccess: 0,
    unsupportedClaims: 0,
    unsafeActions: 0,
    humanEffort: 0,
  });

  // Simulated data fetch - in production, call API
  const fetchData = async () => {
      if (!user?.user_id) return;
      
      try {
        // Fetch metrics from backend API
        const response = await axios.get('/api/v1/tasks/stats', {
          params: { user_id: user.user_id }
        });
        setMetrics(response.data || {
          taskSuccess: 0,
          unsupportedClaims: 0,
          unsafeActions: 0,
          humanEffort: 0,
        });
      } catch (error) {
        // Fallback to simulated data if API fails
        setMetrics({
          taskSuccess: Math.floor(Math.random() * 85) + 15,
          unsupportedClaims: Math.floor(Math.random() * 20),
          unsafeActions: Math.floor(Math.random() * 15),
          humanEffort: Math.floor(Math.random() * 25),
        });
      }

      try {
        // Fetch safety events from backend API
        const response = await axios.get('/api/v1/audit/logs', {
          params: { user_id: user.user_id, limit: 10 }
        });
        setSafetyEvents(response.data || []);
      } catch (error) {
        // Fallback to simulated events if API fails
        const events = [
          { id: 1, type: 'prompt_injection', message: 'Blocked malicious instruction', severity: 'high', time: '2 min ago' },
          { id: 2, type: 'data_protection', message: 'PII redacted successfully', severity: 'medium', time: '5 min ago' },
          { id: 3, type: 'tool_abuse', message: 'Unauthorized tool blocked', severity: 'low', time: '8 min ago' },
        ];
        setSafetyEvents(events);
      }
      
      setLoaded(true);
    };

    fetchData();
  }, [user?.user_id]);

  if (!isAuthenticated) {
    return <>{/* Redirect to login */}</>;
  }

  return (
    <main className="min-h-screen bg-gray-50">
      <Header />
      
      <section className="p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {/* Task Success Rate Card */}
          <Card>
            <CardHeader className="flex justify-between">
              <CardTitle>Task Success Rate</CardTitle>
              <span className="text-sm text-gray-500">{metrics.taskSuccess}%</span>
            </CardHeader>
            <CardContent>
              <div className="mt-4">
                <motion.div
                  animate={{ width: `${metrics.taskSuccess}%` }}
                  transition={{ duration: 1.5, easing: 'easeOut' }}
                  className="bg-blue-500 h-4 rounded-full overflow-hidden"
                >
                  <div className="h-full w-full bg-blue-600"></div>
                </motion.div>
              </div>
            </CardContent>
          </Card>

          {/* Unsupported Claims Card */}
          <Card>
            <CardHeader className="flex justify-between">
              <CardTitle>Unsupported Claim Rate</CardTitle>
              <span className="text-sm text-gray-500">{metrics.unsupportedClaims}%</span>
            </CardHeader>
            <CardContent>
              <div className="mt-4">
                <motion.div
                  animate={{ width: `${100 - metrics.unsupportedClaims}%` }}
                  transition={{ duration: 1.5, easing: 'easeOut' }}
                  className="bg-red-500 h-4 rounded-full overflow-hidden"
                >
                  <div className="h-full bg-green-600 w-full" style={{ width: `${metrics.unsupportedClaims}%` }}></div>
                </motion.div>
              </div>
            </CardContent>
          </Card>

          {/* Safety Violations Card */}
          <Card>
            <CardHeader className="flex justify-between">
              <CardTitle>Safety Violations</CardTitle>
              <span className="text-sm text-gray-500">{metrics.unsafeActions}</span>
            </CardHeader>
            <CardContent>
              <div className="mt-4">
                <motion.div
                  animate={{ width: `${metrics.unsafeActions}%` }}
                  transition={{ duration: 1.5, easing: 'easeOut' }}
                  className="bg-orange-500 h-4 rounded-full overflow-hidden"
                >
                  <div className="h-full bg-orange-600 w-full" style={{ width: `${metrics.unsafeActions}%` }}></div>
                </motion.div>
              </div>
            </CardContent>
          </Card>

          {/* Human Effort Card */}
          <Card>
            <CardHeader className="flex justify-between">
              <CardTitle>Human Effort</CardTitle>
              <span className="text-sm text-gray-500">{metrics.humanEffort}%</span>
            </CardHeader>
            <CardContent>
              <div className="mt-4">
                <motion.div
                  animate={{ width: `${100 - metrics.humanEffort}%` }}
                  transition={{ duration: 1.5, easing: 'easeOut' }}
                  className="bg-yellow-500 h-4 rounded-full overflow-hidden"
                >
                  <div className="h-full bg-yellow-600 w-full" style={{ width: `${100 - metrics.humanEffort}%` }}></div>
                </motion.div>
              </div>
            </CardContent>
          </Card>
        </section>

        <!-- Safety Events Timeline -->
        <section className="mt-8">
          <h2 className="text-lg font-medium text-gray-900 mb-4">
            <Shield className="inline-block mr-2 h-4 w-4" />Safety Events
          </h2>
          <div className="space-y-4 max-h-96 overflow-y-auto">
            {safetyEvents.map((event) => (
              <motion.div
                key={event.id}
                variants={{
                  hidden: { opacity: 0, y: 20 },
                  visible: { opacity: 1, y: 0 },
                }}
                transition={{ delay: event.id * 0.1, duration: 0.5 }}
                className="p-4 rounded-lg border-l-4"
                style={{
                  borderLeftColor: event.severity === 'high' ? 'red-500' : event.severity === 'medium' ? 'orange-500' : 'green-500',
                }}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium text-gray-900">{event.message}</p>
                    <p className="text-xs text-gray-500">{event.time}</p>
                  </div>
                  <span className="text-xs font-bold text-{severity}-600 capitalize">{severity}</span>
                </div>
              </motion.div>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
};
import { Navigate } from 'react-router-dom';

export function AdminClientReadiness() {
  return <Navigate to="/admin/setup" replace />;
}

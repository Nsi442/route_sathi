import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { errorMessage } from '../../api/client';
import { userApi } from '../../api/endpoints';
import UserShell from '../../components/UserShell';
import { Alert, Field } from '../../components/Ui';
import { IconLogout, IconUser } from '../../components/Icons';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { formatDate, initials } from '../../lib/format';

export default function Profile() {
  const { user, setUser, signOut } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();

  const [name, setName] = useState(user?.name || '');
  const [phone, setPhone] = useState(user?.phone || '');
  const [savingProfile, setSavingProfile] = useState(false);

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [savingPassword, setSavingPassword] = useState(false);

  async function saveProfile(event) {
    event.preventDefault();
    setSavingProfile(true);
    try {
      const updated = await userApi.updateProfile({ name: name.trim(), phone: phone.trim() });
      setUser(updated);
      toast.success('Profile updated.');
    } catch (err) {
      toast.error(errorMessage(err, 'Could not save your profile.'));
    } finally {
      setSavingProfile(false);
    }
  }

  async function changePassword(event) {
    event.preventDefault();
    setPasswordError('');
    if (newPassword.length < 8) {
      setPasswordError('Choose a new password with at least 8 characters.');
      return;
    }
    setSavingPassword(true);
    try {
      await userApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword('');
      setNewPassword('');
      toast.success('Password changed.');
    } catch (err) {
      setPasswordError(errorMessage(err, 'Could not change your password.'));
    } finally {
      setSavingPassword(false);
    }
  }

  function handleSignOut() {
    signOut();
    navigate('/login', { replace: true });
  }

  return (
    <UserShell title="Profile" plainHeader narrow>
      <div className="card card-pad mb-3">
        <div className="row">
          <span
            className="choice-icon"
            style={{ width: 54, height: 54, borderRadius: 16, fontSize: '1.1rem', fontWeight: 700 }}
          >
            {initials(user?.name)}
          </span>
          <div className="grow" style={{ minWidth: 0 }}>
            <h2 className="truncate">{user?.name}</h2>
            <p className="small muted truncate">{user?.email}</p>
            <p className="tiny muted mt-2">
              {user?.user_id} · joined {formatDate(user?.created_at)}
            </p>
          </div>
        </div>
      </div>

      <form className="card mb-3" onSubmit={saveProfile}>
        <div className="card-header">
          <h3>Your details</h3>
          <IconUser width={17} height={17} />
        </div>
        <div className="card-body">
          <Field label="Full name" htmlFor="profile-name">
            <input
              id="profile-name"
              className="input"
              value={name}
              minLength={2}
              required
              onChange={(event) => setName(event.target.value)}
            />
          </Field>
          <Field label="Phone number" htmlFor="profile-phone">
            <input
              id="profile-phone"
              className="input"
              type="tel"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              placeholder="+91 98300 00000"
            />
          </Field>
          <Field label="Email address" htmlFor="profile-email" hint="Your email cannot be changed.">
            <input id="profile-email" className="input" value={user?.email || ''} disabled />
          </Field>
          <button type="submit" className="btn btn-primary btn-block" disabled={savingProfile}>
            {savingProfile ? 'Saving…' : 'Save changes'}
          </button>
        </div>
      </form>

      <form className="card mb-3" onSubmit={changePassword}>
        <div className="card-header">
          <h3>Change password</h3>
        </div>
        <div className="card-body">
          {passwordError && (
            <div className="mb-3">
              <Alert tone="error">{passwordError}</Alert>
            </div>
          )}
          <Field label="Current password" htmlFor="current-password">
            <input
              id="current-password"
              className="input"
              type="password"
              autoComplete="current-password"
              required
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
            />
          </Field>
          <Field label="New password" htmlFor="new-password" hint="At least 8 characters.">
            <input
              id="new-password"
              className="input"
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
            />
          </Field>
          <button type="submit" className="btn btn-secondary btn-block" disabled={savingPassword}>
            {savingPassword ? 'Updating…' : 'Update password'}
          </button>
        </div>
      </form>

      <button type="button" className="btn btn-danger btn-block" onClick={handleSignOut}>
        <IconLogout width={17} height={17} /> Sign out
      </button>

      <p className="tiny muted center mt-4">
        RouteSathi · Accessible Places. Better Access.
      </p>
    </UserShell>
  );
}

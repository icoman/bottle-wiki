<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN"
 "http://www.w3.org/TR/html4/strict.dtd">

<html>
<head>
<title>{{title}}</title>
</head>
<body>

<h1>{{title}}</h1>

%if msg:
<font color="red">{{msg}}</font>
%end

<form action="/login" method="post" enctype="multipart/form-data">

<input type="hidden" name="back" value="{{back}}" />

User:
<select name="user">
%for u in users:
<option>{{u}}</option>
%end
</select>
<br>
Password:
<input type="password" name="password">
<br>
<input type="submit" value="Login" />
</form>

</body>
</html>

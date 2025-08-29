# DSP_Final
Data Security and Privacy Final Project Implementation.

**Team Project Description
Class of Data Security and Privacy
Fall 2025
Make sure you read the whole document!**

**1 Total Points**<br>
40 pts

**2 The Goals**<br>
Through this project, you are expected to:
• Learn to use project management tools to help development, especially git (e.g., Github);
• Practice security/privacy demand analysis; and
• Practice selection and application of existing security/privacy enhancement tools.

**3 Background**<br>
Database as a service has become an essential cloud service, and all cloud service providers offer their own
cloud-based database solutions, which provide scalable and reliable database service to end users. It greatly
reduces the user’s efforts to maintain its own database. However, this type of service also brings security
concerns. As the cloud service provider manages the database system on behalf of the user, it is possible
that a malicious insider accesses the stored data without permission. Encrypting data before sending to the
database can solve the security concern. But at the same time, it makes database query hard. The goal of
the project is to design, implement, and evaluate a secure database-as-a-service system. The system should
allow the user to protect its data stored in the database while utilize the cloud.
Here we consider a simplified database, which only includes a single table. The table is about healthcare
information and includes the following fields:
• First name (string)
• Last name (string)
• Gender (boolean)
• Age (integer)
• Weight (floating)
• Height (floating)
• Health history (text)

_One important thing to keep in mind is that we do not fully trust the cloud, and assume the cloud is
semi-trusted, i.e., the cloud will follow any predefined protocol, but at the same time will try its best to
extract information of the database from exchanged messages.
We assume the fields information is not sensitive._

**_4 Project Requirements_**<br>

**4.1 Basic Setup (5 pts total)**<br>
You can choose your own software configuration, but must use a SQL database (e.g., MySQL). It is ok you
run the database on your own computer, and “pretend” to be in the cloud environment.
• Set up the SQL database system (2 pts);
• Create a table with given in Section 3, and fill the table with at least 100 data items (3 pts).

**4.2 Security Features (25 pts total)**<br>
The developed system will be evaluated based on the following features:
• User authentication (5 pts). The system should authenticate a user before the user can do anything.
Make sure you meet the following requirements:
– Using username/password for user authentication;
– The cloud should not store the original password for secure purpose.
Note that you should design and develop your own authentication instead of relying the database
system.
• Basic access control mechanism (5 pts). The system should consider at least two groups of users, one
group (group H) can access all fields and one group (group R) can access all fields except first name
and last name.
– Users from both groups H and R can query existing data stored in the database, but they should
only see attributes they are allowed to see. For example, data items returned to a user of group R
should not include attributes first name and last name;
– Only users from group H can add new data items to the database.
• Basic query integrity protection. The system should allow a user to detect modified query results.
– Single data item integrity (5 pts). If a returned data item is modified or fake, the user should be
able to detect. Make sure consider users from both groups.
– Query completeness (5 pts). If the one or more data items are removed from a query result, the
user should be able to detect, at least with a probability.
• Basic data confidentiality protection (5 pts). Assume the gender and age attributes are sensitive, and
the system should protect them the cloud (or your local database management system).
– To simplify the task, you do not need to worry the cloud querying protected attributes;
– Make sure your protection does not leak statistic information, e.g., percentage of data items with
the same gender.

**4.3 Project report (10 pts total)**<br>
The report should:
• Explain the design of the system with a diagram of the architecture (2 pts);
• For each security features your project implement and given in Section 4.2, explain the way it is
implement and the reason it achieves the specific security feature (3 pts). Note that these points are
for the quality of the project report;
• Explain each team member’s contribution and include his/her Github commit history (2 pts);
• Discuss the limitations of the project (3 pts). You only need to cover security/privacy related
limitations.

**5 The Team**<br>
This is a team project, each team can have 1 to 3 team members.

**6 Submission**<br>
Submit the following items:
• Project report;
• Source code.

**7 Extra Points**<br>
You will receive at most 10 extra points if you finish an extra security feature.
Order preserving encryption is a cryptographic tool that can help to protected numerical attributes of an
outsourced database and support many useful queries, especially these requires range conditions.
• Explain what is order preserving encryption and explain the way it works (2 pts);
• Choosing an order preserving encryption scheme and applying it to the attribute Weight. Your
  implementation should support range queries, i.e., return data items with the weight value in a given
  range (5 pts).
• Document and explain in details your design and implementation (3 pts).
For the extra points, you need to submit:
• A separate report that covers everything mentioned above; and
• Source code of your design.
**You can use an existing library that supports order preserving encryption.**

